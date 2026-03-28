import datetime
import io
import uuid
from dataclasses import dataclass, field

import pytest
from PIL import Image

from src.assets.enums import AssetAccessTypeEnum, AssetStatusEnum, AssetTypeEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.assets.exceptions import AssetNotFound, InvalidAsset
from src.assets.service import AssetService, TaskDispatcher
from src.assets.storage import StoredObject, UploadInstruction, build_asset_storage_key
from src.assets.schemas import AssetInitUploadRequest
from src.config import AssetsSettings


@dataclass
class FakeVariant:
    asset_variant_id: uuid.UUID
    asset_id: uuid.UUID
    asset_variant_type: AssetVariantTypeEnum
    storage_bucket: str
    storage_key: str
    mime_type: str
    size_bytes: int
    width: int | None
    height: int | None
    duration_ms: int | None
    bitrate: int | None
    checksum_sha256: str | None
    is_primary: bool
    status: AssetVariantStatusEnum
    created_at: datetime.datetime


@dataclass
class FakeAsset:
    asset_id: uuid.UUID
    owner_id: uuid.UUID
    asset_type: AssetTypeEnum
    original_filename: str
    original_extension: str | None
    declared_mime_type: str | None
    detected_mime_type: str | None
    size_bytes: int | None
    status: AssetStatusEnum
    access_type: AssetAccessTypeEnum
    asset_metadata: dict[str, object]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None = None
    variants: list[FakeVariant] = field(default_factory=list)


class FakeAssetRepository:
    def __init__(self) -> None:
        self.assets: dict[uuid.UUID, FakeAsset] = {}
        self.active_links: set[uuid.UUID] = set()

    async def create_upload(self, **kwargs) -> FakeAsset:  # type: ignore[no-untyped-def]
        asset = FakeAsset(
            asset_id=kwargs["asset_id"],
            owner_id=kwargs["owner_id"],
            asset_type=kwargs["asset_type"],
            original_filename=kwargs["original_filename"],
            original_extension=kwargs["original_extension"],
            declared_mime_type=kwargs["declared_mime_type"],
            detected_mime_type=None,
            size_bytes=None,
            status=AssetStatusEnum.PENDING_UPLOAD,
            access_type=kwargs["access_type"],
            asset_metadata=kwargs["asset_metadata"],
            created_at=kwargs["now"],
            updated_at=kwargs["now"],
            variants=[
                FakeVariant(
                    asset_variant_id=uuid.uuid4(),
                    asset_id=kwargs["asset_id"],
                    asset_variant_type=AssetVariantTypeEnum.ORIGINAL,
                    storage_bucket=kwargs["storage_bucket"],
                    storage_key=kwargs["storage_key"],
                    mime_type=kwargs["original_mime_type"],
                    size_bytes=0,
                    width=None,
                    height=None,
                    duration_ms=None,
                    bitrate=None,
                    checksum_sha256=None,
                    is_primary=True,
                    status=AssetVariantStatusEnum.PENDING,
                    created_at=kwargs["now"],
                )
            ],
        )
        self.assets[asset.asset_id] = asset
        return asset

    async def get_asset(
        self,
        *,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> FakeAsset | None:
        asset = self.assets.get(asset_id)
        if asset is None:
            return None
        if owner_id is not None and asset.owner_id != owner_id:
            return None
        return asset

    async def update_after_finalize(self, **kwargs) -> FakeAsset:  # type: ignore[no-untyped-def]
        asset = self.assets[kwargs["asset_id"]]
        asset.size_bytes = kwargs["size_bytes"]
        asset.status = kwargs["status"]
        asset.updated_at = kwargs["now"]
        asset.variants[0].size_bytes = kwargs["size_bytes"]
        asset.variants[0].mime_type = kwargs["original_mime_type"]
        asset.variants[0].status = AssetVariantStatusEnum.READY
        return asset

    async def set_asset_processing(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        asset = self.assets[kwargs["asset_id"]]
        asset.status = AssetStatusEnum.PROCESSING
        asset.updated_at = kwargs["now"]

    async def set_asset_ready(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        asset = self.assets[kwargs["asset_id"]]
        asset.status = AssetStatusEnum.READY
        asset.detected_mime_type = kwargs["detected_mime_type"]
        asset.updated_at = kwargs["now"]

    async def set_asset_failed(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        asset = self.assets[kwargs["asset_id"]]
        asset.status = AssetStatusEnum.FAILED
        asset.asset_metadata["last_processing_error"] = kwargs["error_message"]
        asset.updated_at = kwargs["now"]
        for variant in asset.variants[1:]:
            variant.status = AssetVariantStatusEnum.FAILED

    async def upsert_variant(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        asset = self.assets[kwargs["asset_id"]]
        existing = next(
            (
                variant
                for variant in asset.variants
                if variant.asset_variant_type == kwargs["asset_variant_type"]
            ),
            None,
        )
        if existing is None:
            asset.variants.append(
                FakeVariant(
                    asset_variant_id=uuid.uuid4(),
                    asset_id=kwargs["asset_id"],
                    asset_variant_type=kwargs["asset_variant_type"],
                    storage_bucket=kwargs["storage_bucket"],
                    storage_key=kwargs["storage_key"],
                    mime_type=kwargs["mime_type"],
                    size_bytes=kwargs["size_bytes"],
                    width=kwargs["width"],
                    height=kwargs["height"],
                    duration_ms=kwargs["duration_ms"],
                    bitrate=kwargs["bitrate"],
                    checksum_sha256=kwargs["checksum_sha256"],
                    is_primary=kwargs["is_primary"],
                    status=kwargs["status"],
                    created_at=datetime.datetime.now(datetime.timezone.utc),
                )
            )
            return

        existing.storage_bucket = kwargs["storage_bucket"]
        existing.storage_key = kwargs["storage_key"]
        existing.mime_type = kwargs["mime_type"]
        existing.size_bytes = kwargs["size_bytes"]
        existing.width = kwargs["width"]
        existing.height = kwargs["height"]
        existing.duration_ms = kwargs["duration_ms"]
        existing.bitrate = kwargs["bitrate"]
        existing.checksum_sha256 = kwargs["checksum_sha256"]
        existing.is_primary = kwargs["is_primary"]
        existing.status = kwargs["status"]

    async def mark_asset_deleted(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        asset = self.assets[kwargs["asset_id"]]
        asset.status = AssetStatusEnum.DELETED
        asset.deleted_at = kwargs["now"]
        asset.updated_at = kwargs["now"]
        for variant in asset.variants:
            variant.status = AssetVariantStatusEnum.DELETED

    async def get_stale_pending_uploads(self, **kwargs) -> list[FakeAsset]:  # type: ignore[no-untyped-def]
        cutoff = kwargs["created_before"]
        return [
            asset
            for asset in self.assets.values()
            if asset.status == AssetStatusEnum.PENDING_UPLOAD and asset.created_at <= cutoff
        ]

    async def get_orphaned_assets(self, **kwargs) -> list[FakeAsset]:  # type: ignore[no-untyped-def]
        cutoff = kwargs["orphaned_before"]
        return [
            asset
            for asset in self.assets.values()
            if asset.asset_metadata.get("orphaned_at")
            and datetime.datetime.fromisoformat(asset.asset_metadata["orphaned_at"]) <= cutoff
        ]

    async def get_failed_assets(self, **kwargs) -> list[FakeAsset]:  # type: ignore[no-untyped-def]
        cutoff = kwargs["updated_before"]
        return [
            asset
            for asset in self.assets.values()
            if asset.status == AssetStatusEnum.FAILED and asset.updated_at <= cutoff
        ]

    async def asset_has_active_links(self, **kwargs) -> bool:  # type: ignore[no-untyped-def]
        return kwargs["asset_id"] in self.active_links

    async def mark_orphaned(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        asset = self.assets[kwargs["asset_id"]]
        asset.asset_metadata["orphaned_at"] = kwargs["orphaned_at"]
        asset.updated_at = kwargs["now"]


class FakeStorage:
    def __init__(self) -> None:
        self.private_bucket = "nerdex-dev-private"
        self.put_requests: list[tuple[str, str, str | None]] = []
        self.get_requests: list[tuple[str, str]] = []
        self.head_map: dict[tuple[str, str], tuple[int, str]] = {}
        self.object_payloads: dict[tuple[str, str], bytes] = {}
        self.uploaded_objects: dict[tuple[str, str], bytes] = {}
        self.deleted_objects: list[tuple[str, str]] = []

    async def generate_presigned_put(self, *, bucket: str, key: str, mime_type: str | None) -> UploadInstruction:
        self.put_requests.append((bucket, key, mime_type))
        return UploadInstruction(
            bucket=bucket,
            key=key,
            url=f"https://upload.test/{bucket}/{key}",
            headers={"Content-Type": mime_type} if mime_type else {},
            expires_in_seconds=900,
        )

    async def generate_presigned_get(
        self,
        *,
        bucket: str,
        key: str,
        download_filename: str | None = None,
        inline: bool = True,
        response_content_type: str | None = None,
    ) -> str:
        self.get_requests.append((bucket, key))
        return f"https://download.test/{bucket}/{key}"

    async def head_object(self, *, bucket: str, key: str):  # type: ignore[no-untyped-def]
        metadata = self.head_map.get((bucket, key))
        if metadata is None:
            return None

        class Head:
            def __init__(self, bucket: str, key: str, size_bytes: int, mime_type: str) -> None:
                self.bucket = bucket
                self.key = key
                self.size_bytes = size_bytes
                self.mime_type = mime_type
                self.etag = None

        return Head(bucket, key, metadata[0], metadata[1])

    async def get_object_bytes(self, *, bucket: str, key: str) -> bytes:
        return self.object_payloads[(bucket, key)]

    async def upload_bytes(self, *, bucket: str, key: str, payload: bytes, mime_type: str) -> StoredObject:
        self.uploaded_objects[(bucket, key)] = payload
        return StoredObject(
            size_bytes=len(payload),
            checksum_sha256="checksum",
            mime_type=mime_type,
        )

    async def delete_object(self, *, bucket: str, key: str) -> None:
        self.deleted_objects.append((bucket, key))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def build_service() -> tuple[AssetService, FakeAssetRepository, FakeStorage, list[uuid.UUID], list[uuid.UUID]]:
    repository = FakeAssetRepository()
    storage = FakeStorage()
    image_queue: list[uuid.UUID] = []
    video_queue: list[uuid.UUID] = []
    service = AssetService(
        repository=repository,  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
        settings=AssetsSettings(),
        task_dispatcher=TaskDispatcher(
            enqueue_image_processing=lambda asset_id: image_queue.append(asset_id),
            enqueue_video_processing=lambda asset_id: video_queue.append(asset_id),
        ),
    )
    return service, repository, storage, image_queue, video_queue


def make_png_bytes(size: tuple[int, int] = (1024, 768)) -> bytes:
    image = Image.new("RGB", size, color="red")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.anyio
async def test_init_upload_creates_asset_and_original_variant() -> None:
    service, repository, _, _, _ = build_service()
    owner_id = uuid.uuid4()

    response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )

    asset = repository.assets[response.asset.asset_id]
    assert asset.owner_id == owner_id
    assert asset.status == AssetStatusEnum.PENDING_UPLOAD
    assert asset.asset_metadata["usage_context"] == "avatar"
    assert asset.variants[0].asset_variant_type == AssetVariantTypeEnum.ORIGINAL
    assert asset.variants[0].storage_key.endswith("/original.png")


@pytest.mark.anyio
async def test_finalize_upload_moves_image_asset_to_processing_and_dispatches_task() -> None:
    service, repository, storage, image_queue, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="post_attachment",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    original_variant = asset.variants[0]
    storage.head_map[(original_variant.storage_bucket, original_variant.storage_key)] = (1024, "image/png")

    response = await service.finalize_upload(owner_id=owner_id, asset_id=asset.asset_id)

    assert response.asset.status == AssetStatusEnum.PROCESSING
    assert image_queue == [asset.asset_id]
    assert repository.assets[asset.asset_id].variants[0].status == AssetVariantStatusEnum.READY


@pytest.mark.anyio
async def test_finalize_upload_marks_file_asset_ready_without_queue() -> None:
    service, repository, storage, image_queue, video_queue = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="document.pdf",
            size_bytes=1024,
            declared_mime_type="application/pdf",
            asset_type=AssetTypeEnum.FILE,
            usage_context="attachment",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    original_variant = asset.variants[0]
    storage.head_map[(original_variant.storage_bucket, original_variant.storage_key)] = (2048, "application/pdf")

    response = await service.finalize_upload(owner_id=owner_id, asset_id=asset.asset_id)

    assert response.asset.status == AssetStatusEnum.READY
    assert image_queue == []
    assert video_queue == []


@pytest.mark.anyio
async def test_storage_key_generation_matches_asset_centric_pattern() -> None:
    asset_id = uuid.UUID("ab12ab12-ab12-ab12-ab12-ab12ab12ab12")

    storage_key = build_asset_storage_key(
        asset_id=asset_id,
        variant_type=AssetVariantTypeEnum.AVATAR_MEDIUM,
        extension="webp",
    )

    assert storage_key == "v1/assets/ab/ab12ab12-ab12-ab12-ab12-ab12ab12ab12/avatar_medium.webp"


@pytest.mark.anyio
async def test_asset_type_validation_accepts_gif_as_image() -> None:
    service, _, _, _, _ = build_service()

    response = await service.init_upload(
        owner_id=uuid.uuid4(),
        data=AssetInitUploadRequest(
            filename="animated.gif",
            size_bytes=1024,
            declared_mime_type="image/gif",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )

    assert response.asset.asset_type == AssetTypeEnum.IMAGE


@pytest.mark.anyio
async def test_asset_type_validation_rejects_mismatched_video_mime() -> None:
    service, _, _, _, _ = build_service()

    with pytest.raises(InvalidAsset):
        await service.init_upload(
            owner_id=uuid.uuid4(),
            data=AssetInitUploadRequest(
                filename="photo.png",
                size_bytes=1024,
                declared_mime_type="image/png",
                asset_type=AssetTypeEnum.VIDEO,
                usage_context="post_attachment",
            ),
        )


@pytest.mark.anyio
async def test_process_image_asset_creates_expected_variants() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    original_variant = asset.variants[0]
    storage.object_payloads[(original_variant.storage_bucket, original_variant.storage_key)] = make_png_bytes()

    await repository.set_asset_processing(asset_id=asset.asset_id, now=datetime.datetime.now(datetime.timezone.utc))
    await service.process_image_asset(asset_id=asset.asset_id)

    variant_types = {variant.asset_variant_type for variant in repository.assets[asset.asset_id].variants}
    assert {
        AssetVariantTypeEnum.ORIGINAL,
        AssetVariantTypeEnum.IMAGE_MEDIUM,
        AssetVariantTypeEnum.IMAGE_SMALL,
    } == variant_types
    assert repository.assets[asset.asset_id].status == AssetStatusEnum.READY


@pytest.mark.anyio
async def test_generate_avatar_variants_creates_expected_square_variants() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    asset.status = AssetStatusEnum.READY
    asset.variants[0].status = AssetVariantStatusEnum.READY
    original_variant = asset.variants[0]
    storage.object_payloads[(original_variant.storage_bucket, original_variant.storage_key)] = make_png_bytes()

    await service.generate_avatar_variants(
        asset_id=asset.asset_id,
        owner_id=owner_id,
        crop={"x": 0.1, "y": 0.05, "size": 0.6},
    )

    variant_types = {variant.asset_variant_type for variant in repository.assets[asset.asset_id].variants}
    assert AssetVariantTypeEnum.AVATAR_MEDIUM in variant_types
    assert AssetVariantTypeEnum.AVATAR_SMALL in variant_types


@pytest.mark.anyio
async def test_generate_avatar_variants_rejects_foreign_asset() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    asset.status = AssetStatusEnum.READY
    asset.variants[0].status = AssetVariantStatusEnum.READY
    original_variant = asset.variants[0]
    storage.object_payloads[(original_variant.storage_bucket, original_variant.storage_key)] = make_png_bytes()

    with pytest.raises(AssetNotFound):
        await service.generate_avatar_variants(
            asset_id=asset.asset_id,
            owner_id=other_user_id,
            crop={"x": 0.1, "y": 0.1, "size": 0.7},
        )


@pytest.mark.anyio
async def test_generate_avatar_variants_rejects_non_image_asset() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="document.pdf",
            size_bytes=1024,
            declared_mime_type="application/pdf",
            asset_type=AssetTypeEnum.FILE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    asset.status = AssetStatusEnum.READY
    asset.variants[0].status = AssetVariantStatusEnum.READY
    original_variant = asset.variants[0]
    storage.object_payloads[(original_variant.storage_bucket, original_variant.storage_key)] = b"pdf"

    with pytest.raises(InvalidAsset):
        await service.generate_avatar_variants(
            asset_id=asset.asset_id,
            owner_id=owner_id,
            crop={"x": 0.1, "y": 0.1, "size": 0.7},
        )


@pytest.mark.anyio
async def test_generate_avatar_variants_rejects_invalid_crop() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    asset.status = AssetStatusEnum.READY
    asset.variants[0].status = AssetVariantStatusEnum.READY
    original_variant = asset.variants[0]
    storage.object_payloads[(original_variant.storage_bucket, original_variant.storage_key)] = make_png_bytes()

    with pytest.raises(InvalidAsset):
        await service.generate_avatar_variants(
            asset_id=asset.asset_id,
            owner_id=owner_id,
            crop={"x": 0.7, "y": 0.7, "size": 0.6},
        )


@pytest.mark.anyio
async def test_generate_avatar_variants_rejects_tiny_crop() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    asset.status = AssetStatusEnum.READY
    asset.variants[0].status = AssetVariantStatusEnum.READY
    original_variant = asset.variants[0]
    storage.object_payloads[(original_variant.storage_bucket, original_variant.storage_key)] = make_png_bytes(
        size=(240, 240),
    )

    with pytest.raises(InvalidAsset):
        await service.generate_avatar_variants(
            asset_id=asset.asset_id,
            owner_id=owner_id,
            crop={"x": 0.2, "y": 0.2, "size": 0.3},
        )


@pytest.mark.anyio
async def test_failed_processing_marks_asset_failed() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    original_variant = asset.variants[0]
    storage.object_payloads[(original_variant.storage_bucket, original_variant.storage_key)] = b"not-an-image"

    await repository.set_asset_processing(asset_id=asset.asset_id, now=datetime.datetime.now(datetime.timezone.utc))
    with pytest.raises(Exception):
        await service.process_image_asset(asset_id=asset.asset_id)

    assert repository.assets[asset.asset_id].status == AssetStatusEnum.FAILED


@pytest.mark.anyio
async def test_cleanup_job_picks_orphaned_assets() -> None:
    service, repository, _, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    asset.status = AssetStatusEnum.READY
    asset.asset_metadata["orphaned_at"] = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    ).isoformat()

    deleted_ids = await service.cleanup_orphaned_assets()

    assert deleted_ids == [asset.asset_id]
    assert repository.assets[asset.asset_id].status == AssetStatusEnum.DELETED


@pytest.mark.anyio
async def test_cleanup_logic_does_not_delete_asset_with_active_links() -> None:
    service, repository, _, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    asset.status = AssetStatusEnum.READY
    asset.asset_metadata["orphaned_at"] = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=48)
    ).isoformat()
    repository.active_links.add(asset.asset_id)

    deleted_ids = await service.cleanup_orphaned_assets()

    assert deleted_ids == []
    assert repository.assets[asset.asset_id].status == AssetStatusEnum.READY


@pytest.mark.anyio
async def test_presigned_upload_and_download_instructions_work() -> None:
    service, repository, storage, _, _ = build_service()
    owner_id = uuid.uuid4()
    init_response = await service.init_upload(
        owner_id=owner_id,
        data=AssetInitUploadRequest(
            filename="document.pdf",
            size_bytes=1024,
            declared_mime_type="application/pdf",
            asset_type=AssetTypeEnum.FILE,
            usage_context="attachment",
        ),
    )
    asset = repository.assets[init_response.asset.asset_id]
    original_variant = asset.variants[0]
    storage.head_map[(original_variant.storage_bucket, original_variant.storage_key)] = (2048, "application/pdf")
    await service.finalize_upload(owner_id=owner_id, asset_id=asset.asset_id)

    asset_get = await service.get_asset(asset_id=asset.asset_id, owner_id=owner_id)

    assert init_response.upload_url.startswith("https://upload.test/")
    assert asset_get.variants[0].url == f"https://download.test/{original_variant.storage_bucket}/{original_variant.storage_key}"


@pytest.mark.anyio
async def test_new_assets_foundation_does_not_use_legacy_s3_path(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.s3.utils

    async def fail_legacy_upload(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("legacy s3 upload should not be used")

    monkeypatch.setattr(src.s3.utils, "upload_file", fail_legacy_upload)
    service, _, _, _, _ = build_service()

    response = await service.init_upload(
        owner_id=uuid.uuid4(),
        data=AssetInitUploadRequest(
            filename="photo.png",
            size_bytes=1024,
            declared_mime_type="image/png",
            asset_type=AssetTypeEnum.IMAGE,
            usage_context="avatar",
        ),
    )

    assert response.asset.status == AssetStatusEnum.PENDING_UPLOAD
