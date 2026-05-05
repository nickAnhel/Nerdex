from __future__ import annotations

import datetime
import io
import mimetypes
import typing as tp
import uuid
from dataclasses import dataclass
import tempfile
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from src.assets.enums import (
    AssetAccessTypeEnum,
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
)
from src.assets.exceptions import AssetNotFound, AssetUploadNotReady, InvalidAsset
from src.assets.models import AssetModel
from src.assets.repository import AssetRepository
from src.assets.schemas import AssetFinalizeUploadResponse, AssetGet, AssetInitUploadRequest, AssetInitUploadResponse, AssetVariantGet
from src.assets.storage import AssetStorage, build_asset_storage_key, detect_extension, guess_mime_type
from src.assets.video_processing import VideoMetadata, VideoProcessingError, VideoProcessor
from src.config import AssetsSettings
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum


GENERIC_IMAGE_VARIANTS: dict[AssetVariantTypeEnum, tuple[int, int]] = {
    AssetVariantTypeEnum.IMAGE_MEDIUM: (1280, 1280),
    AssetVariantTypeEnum.IMAGE_SMALL: (640, 640),
}

AVATAR_VARIANTS: dict[AssetVariantTypeEnum, tuple[int, int]] = {
    AssetVariantTypeEnum.AVATAR_MEDIUM: (256, 256),
    AssetVariantTypeEnum.AVATAR_SMALL: (96, 96),
}
AVATAR_ALLOWED_ASSET_STATUSES = {
    AssetStatusEnum.UPLOADED,
    AssetStatusEnum.PROCESSING,
    AssetStatusEnum.READY,
}
MIN_AVATAR_CROP_SIZE_PX = 96

IMAGE_FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


@dataclass(slots=True)
class TaskDispatcher:
    enqueue_image_processing: tp.Callable[[uuid.UUID], None]
    enqueue_video_processing: tp.Callable[[uuid.UUID], None]


@dataclass(slots=True)
class AssetVideoProcessingUpdate:
    asset_id: uuid.UUID
    processing_status: VideoProcessingStatusEnum
    duration_seconds: int | None = None
    width: int | None = None
    height: int | None = None
    orientation: VideoOrientationEnum | None = None
    available_quality_metadata: dict[str, object] | None = None
    processing_error: str | None = None


class VideoProcessingNotifier(tp.Protocol):
    async def notify(self, update: AssetVideoProcessingUpdate) -> None:
        ...


@dataclass(slots=True)
class RenderedImageVariant:
    payload: bytes
    width: int
    height: int


@dataclass(slots=True)
class AvatarCropSpec:
    x: float
    y: float
    size: float


class AssetService:
    def __init__(
        self,
        repository: AssetRepository,
        storage: AssetStorage,
        settings: AssetsSettings,
        task_dispatcher: TaskDispatcher | None = None,
        video_processing_notifier: VideoProcessingNotifier | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._settings = settings
        self._task_dispatcher = task_dispatcher
        self._video_processing_notifier = video_processing_notifier

    async def init_upload(
        self,
        *,
        owner_id: uuid.UUID,
        data: AssetInitUploadRequest,
    ) -> AssetInitUploadResponse:
        self._validate_upload_request(data)
        now = self._now()
        extension = detect_extension(data.filename)
        original_mime_type = guess_mime_type(data.filename, data.declared_mime_type) or "application/octet-stream"
        asset_id = uuid.uuid4()
        storage_key = build_asset_storage_key(
            asset_id=asset_id,
            variant_type=AssetVariantTypeEnum.ORIGINAL,
            extension=extension or self._default_extension(data.asset_type, original_mime_type),
        )
        upload = await self._storage.generate_presigned_put(
            bucket=self._storage.private_bucket,
            key=storage_key,
            mime_type=original_mime_type,
        )
        metadata = {"usage_context": data.usage_context} if data.usage_context else {}
        asset = await self._repository.create_upload(
            asset_id=asset_id,
            owner_id=owner_id,
            asset_type=data.asset_type,
            original_filename=data.filename,
            original_extension=extension,
            declared_mime_type=data.declared_mime_type,
            access_type=AssetAccessTypeEnum.PRIVATE,
            asset_metadata=metadata,
            storage_bucket=upload.bucket,
            storage_key=upload.key,
            original_mime_type=original_mime_type,
            now=now,
        )
        return AssetInitUploadResponse(
            asset=await self._build_asset_get(asset),
            upload_url=upload.url,
            upload_headers=upload.headers,
            expires_in_seconds=upload.expires_in_seconds,
        )

    async def finalize_upload(
        self,
        *,
        owner_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> AssetFinalizeUploadResponse:
        asset = await self._require_owned_asset(asset_id=asset_id, owner_id=owner_id)
        if asset.status != AssetStatusEnum.PENDING_UPLOAD:
            raise AssetUploadNotReady(f"Asset {asset_id} is already finalized")

        original_variant = next(
            (variant for variant in asset.variants if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL),
            None,
        )
        if original_variant is None:
            raise AssetUploadNotReady(f"Asset {asset_id} has no original variant")

        object_head = await self._storage.head_object(
            bucket=original_variant.storage_bucket,
            key=original_variant.storage_key,
        )
        if object_head is None:
            raise AssetUploadNotReady(f"Uploaded object for asset {asset_id} was not found")

        next_status = AssetStatusEnum.READY if asset.asset_type == AssetTypeEnum.FILE else AssetStatusEnum.UPLOADED
        asset = await self._repository.update_after_finalize(
            asset_id=asset_id,
            size_bytes=object_head.size_bytes,
            original_mime_type=object_head.mime_type or original_variant.mime_type,
            status=next_status,
            now=self._now(),
        )

        if asset.asset_type == AssetTypeEnum.IMAGE:
            await self._repository.set_asset_processing(asset_id=asset_id, now=self._now())
            self._dispatch_image_processing(asset_id)
            asset = await self._require_owned_asset(asset_id=asset_id, owner_id=owner_id)
        elif asset.asset_type == AssetTypeEnum.VIDEO:
            await self._repository.set_asset_processing(asset_id=asset_id, now=self._now())
            self._dispatch_video_processing(asset_id)
            asset = await self._require_owned_asset(asset_id=asset_id, owner_id=owner_id)
        else:
            await self._repository.set_asset_ready(
                asset_id=asset_id,
                detected_mime_type=object_head.mime_type,
                now=self._now(),
            )
            asset = await self._require_owned_asset(asset_id=asset_id, owner_id=owner_id)

        return AssetFinalizeUploadResponse(asset=await self._build_asset_get(asset))

    async def get_asset(
        self,
        *,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> AssetGet:
        asset = await self._require_owned_asset(asset_id=asset_id, owner_id=owner_id)
        return await self._build_asset_get(asset)

    async def process_image_asset(
        self,
        *,
        asset_id: uuid.UUID,
    ) -> None:
        asset = await self._repository.get_asset(asset_id=asset_id)
        if asset is None:
            raise AssetNotFound(f"Asset {asset_id} not found")

        original_variant = next(
            variant for variant in asset.variants if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL
        )
        try:
            payload = await self._storage.get_object_bytes(
                bucket=original_variant.storage_bucket,
                key=original_variant.storage_key,
            )
            image = self._load_image(payload)
            detected_mime_type = IMAGE_FORMAT_TO_MIME.get(image.format or "", original_variant.mime_type)

            for variant_type, size in GENERIC_IMAGE_VARIANTS.items():
                rendered = self._render_variant(image=image, size=size)
                extension = "webp"
                storage_key = build_asset_storage_key(
                    asset_id=asset.asset_id,
                    variant_type=variant_type,
                    extension=extension,
                )
                stored = await self._storage.upload_bytes(
                    bucket=self._storage.private_bucket,
                    key=storage_key,
                    payload=rendered.payload,
                    mime_type="image/webp",
                )
                await self._repository.upsert_variant(
                    asset_id=asset.asset_id,
                    asset_variant_type=variant_type,
                    storage_bucket=self._storage.private_bucket,
                    storage_key=storage_key,
                    mime_type=stored.mime_type,
                    size_bytes=stored.size_bytes,
                    width=rendered.width,
                    height=rendered.height,
                    duration_ms=None,
                    bitrate=None,
                    checksum_sha256=stored.checksum_sha256,
                    is_primary=False,
                    status=AssetVariantStatusEnum.READY,
                )

            await self._repository.set_asset_ready(
                asset_id=asset.asset_id,
                detected_mime_type=detected_mime_type,
                now=self._now(),
            )
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            await self._repository.set_asset_failed(
                asset_id=asset.asset_id,
                error_message=str(exc),
                now=self._now(),
            )
            raise

    async def generate_avatar_variants(
        self,
        *,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID,
        crop: dict[str, tp.Any],
    ) -> None:
        asset = await self._require_owned_asset(asset_id=asset_id, owner_id=owner_id)
        original_variant = self._require_avatar_source_asset(asset)
        crop_spec = AvatarCropSpec(**crop)

        payload = await self._storage.get_object_bytes(
            bucket=original_variant.storage_bucket,
            key=original_variant.storage_key,
        )
        rendered_variants = self._render_avatar_variants(payload, crop_spec)

        for variant_type, rendered in rendered_variants.items():
            storage_key = build_asset_storage_key(
                asset_id=asset.asset_id,
                variant_type=variant_type,
                extension="webp",
            )
            stored = await self._storage.upload_bytes(
                bucket=self._storage.private_bucket,
                key=storage_key,
                payload=rendered.payload,
                mime_type="image/webp",
            )
            await self._repository.upsert_variant(
                asset_id=asset.asset_id,
                asset_variant_type=variant_type,
                storage_bucket=self._storage.private_bucket,
                storage_key=storage_key,
                mime_type=stored.mime_type,
                size_bytes=stored.size_bytes,
                width=rendered.width,
                height=rendered.height,
                duration_ms=None,
                bitrate=None,
                checksum_sha256=stored.checksum_sha256,
                is_primary=False,
                status=AssetVariantStatusEnum.READY,
                variant_metadata={"crop": crop},
            )

    async def process_video_asset(
        self,
        *,
        asset_id: uuid.UUID,
    ) -> None:
        asset = await self._repository.get_asset(asset_id=asset_id)
        if asset is None:
            raise AssetNotFound(f"Asset {asset_id} not found")

        original_variant = next(
            variant for variant in asset.variants if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL
        )
        detected_mime_type = (
            asset.detected_mime_type
            or original_variant.mime_type
            or mimetypes.guess_type(asset.original_filename or "")[0]
        )
        processor = VideoProcessor()
        metadata: VideoMetadata | None = None
        quality_metadata: dict[str, object] = {}

        try:
            await self._set_video_processing_status(
                asset=asset,
                processing_status=VideoProcessingStatusEnum.UPLOADED,
                detected_mime_type=detected_mime_type,
            )
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                extension = asset.original_extension or self._default_extension(AssetTypeEnum.VIDEO, detected_mime_type)
                input_path = tmp_path / f"source.{extension}"
                await self._storage.download_to_file(
                    bucket=original_variant.storage_bucket,
                    key=original_variant.storage_key,
                    path=input_path,
                )

                await self._set_video_processing_status(
                    asset=asset,
                    processing_status=VideoProcessingStatusEnum.METADATA_EXTRACTING,
                    detected_mime_type=detected_mime_type,
                )
                metadata = await processor.probe(input_path)
                quality_metadata = self._quality_metadata_for_original(
                    original_variant=original_variant,
                    metadata=metadata,
                )
                await self._repository.upsert_variant(
                    asset_id=asset.asset_id,
                    asset_variant_type=AssetVariantTypeEnum.ORIGINAL,
                    storage_bucket=original_variant.storage_bucket,
                    storage_key=original_variant.storage_key,
                    mime_type=detected_mime_type or original_variant.mime_type,
                    size_bytes=original_variant.size_bytes,
                    width=metadata.width,
                    height=metadata.height,
                    duration_ms=metadata.duration_seconds * 1000,
                    bitrate=metadata.bitrate,
                    checksum_sha256=original_variant.checksum_sha256,
                    is_primary=True,
                    status=AssetVariantStatusEnum.READY,
                    variant_metadata={"quality": "original"},
                )

                await self._set_video_processing_status(
                    asset=asset,
                    processing_status=VideoProcessingStatusEnum.TRANSCODING,
                    metadata=metadata,
                    available_quality_metadata=quality_metadata,
                    detected_mime_type=detected_mime_type,
                )
                rendered_variants = await processor.transcode_variants(
                    input_path=input_path,
                    output_dir=tmp_path,
                    metadata=metadata,
                )
                for rendered in rendered_variants:
                    storage_key = build_asset_storage_key(
                        asset_id=asset.asset_id,
                        variant_type=rendered.variant_type,
                        extension="mp4",
                    )
                    stored = await self._storage.upload_file(
                        bucket=self._storage.private_bucket,
                        key=storage_key,
                        path=rendered.path,
                        mime_type="video/mp4",
                    )
                    await self._repository.upsert_variant(
                        asset_id=asset.asset_id,
                        asset_variant_type=rendered.variant_type,
                        storage_bucket=self._storage.private_bucket,
                        storage_key=storage_key,
                        mime_type=stored.mime_type,
                        size_bytes=stored.size_bytes,
                        width=rendered.width,
                        height=rendered.height,
                        duration_ms=metadata.duration_seconds * 1000,
                        bitrate=rendered.bitrate,
                        checksum_sha256=stored.checksum_sha256,
                        is_primary=False,
                        status=AssetVariantStatusEnum.READY,
                        variant_metadata={
                            "quality": rendered.label,
                            "codec": "h264",
                            "container": "mp4",
                        },
                    )
                    quality_metadata[rendered.label] = {
                        "variant_type": rendered.variant_type.value,
                        "width": rendered.width,
                        "height": rendered.height,
                        "mime_type": stored.mime_type,
                        "size_bytes": stored.size_bytes,
                    }

            await self._set_video_processing_status(
                asset=asset,
                processing_status=VideoProcessingStatusEnum.READY,
                metadata=metadata,
                available_quality_metadata=quality_metadata,
                detected_mime_type=detected_mime_type,
            )
            await self._repository.set_asset_ready(
                asset_id=asset.asset_id,
                detected_mime_type=detected_mime_type,
                now=self._now(),
            )
        except (VideoProcessingError, OSError, ValueError) as exc:
            await self._repository.set_asset_failed(
                asset_id=asset.asset_id,
                error_message=str(exc),
                now=self._now(),
            )
            await self._set_video_processing_status(
                asset=asset,
                processing_status=VideoProcessingStatusEnum.FAILED,
                metadata=metadata,
                available_quality_metadata=quality_metadata,
                detected_mime_type=detected_mime_type,
                processing_error=str(exc),
            )
            raise

    async def cleanup_stale_uploads(self) -> list[uuid.UUID]:
        cutoff = self._now() - datetime.timedelta(hours=self._settings.stale_upload_grace_hours)
        assets = await self._repository.get_stale_pending_uploads(created_before=cutoff)
        deleted: list[uuid.UUID] = []
        for asset in assets:
            await self._delete_asset_objects(asset)
            deleted.append(asset.asset_id)
        return deleted

    async def cleanup_orphaned_assets(self) -> list[uuid.UUID]:
        cutoff = self._now() - datetime.timedelta(hours=self._settings.orphan_grace_hours)
        assets = await self._repository.get_orphaned_assets(orphaned_before=cutoff)
        deleted: list[uuid.UUID] = []
        for asset in assets:
            if await self._repository.asset_has_active_links(asset_id=asset.asset_id):
                continue
            await self._delete_asset_objects(asset)
            deleted.append(asset.asset_id)
        return deleted

    async def reconcile_failed_assets(self) -> list[uuid.UUID]:
        cutoff = self._now() - datetime.timedelta(hours=self._settings.stale_upload_grace_hours)
        assets = await self._repository.get_failed_assets(updated_before=cutoff)
        deleted: list[uuid.UUID] = []
        for asset in assets:
            if await self._repository.asset_has_active_links(asset_id=asset.asset_id):
                continue
            await self._delete_asset_objects(asset)
            deleted.append(asset.asset_id)
        return deleted

    async def mark_asset_orphaned_if_unreferenced(
        self,
        *,
        asset_id: uuid.UUID,
    ) -> bool:
        if await self._repository.asset_has_active_links(asset_id=asset_id):
            return False
        await self._repository.mark_orphaned(
            asset_id=asset_id,
            orphaned_at=self._now().isoformat(),
            now=self._now(),
        )
        return True

    async def _build_asset_get(
        self,
        asset: AssetModel,
    ) -> AssetGet:
        variants: list[AssetVariantGet] = []
        for variant in sorted(asset.variants, key=lambda item: item.created_at):
            url = None
            if variant.status == AssetVariantStatusEnum.READY:
                url = await self._storage.generate_presigned_get(
                    bucket=variant.storage_bucket,
                    key=variant.storage_key,
                )
            variants.append(
                AssetVariantGet(
                    asset_variant_type=variant.asset_variant_type,
                    mime_type=variant.mime_type,
                    size_bytes=variant.size_bytes,
                    width=variant.width,
                    height=variant.height,
                    duration_ms=variant.duration_ms,
                    status=variant.status,
                    url=url,
                )
            )

        return AssetGet(
            asset_id=asset.asset_id,
            asset_type=asset.asset_type,
            status=asset.status,
            original_filename=asset.original_filename,
            size_bytes=asset.size_bytes,
            access_type=asset.access_type,
            variants=variants,
            created_at=asset.created_at,
            updated_at=asset.updated_at,
        )

    def _validate_upload_request(self, data: AssetInitUploadRequest) -> None:
        declared_mime_type = (data.declared_mime_type or "").lower()
        extension = detect_extension(data.filename)

        if data.asset_type == AssetTypeEnum.IMAGE:
            if not self._is_declared_image(extension=extension, declared_mime_type=declared_mime_type):
                raise InvalidAsset("Asset type image requires an image mime type or extension")
            max_size = self._settings.max_image_size_mb * 1024 * 1024
        elif data.asset_type == AssetTypeEnum.VIDEO:
            if declared_mime_type and not declared_mime_type.startswith("video/"):
                raise InvalidAsset("Asset type video requires a video mime type")
            if extension not in {"mp4", "webm", "mov"} and declared_mime_type not in {
                "video/mp4",
                "video/webm",
                "video/quicktime",
                "video/x-quicktime",
            }:
                raise InvalidAsset("Video uploads must be mp4, webm, or mov")
            max_size = self._settings.max_video_size_mb * 1024 * 1024
        else:
            max_size = self._settings.max_file_size_mb * 1024 * 1024

        if data.size_bytes > max_size:
            raise InvalidAsset(f"Asset size exceeds limit for {data.asset_type.value}")

    async def _require_owned_asset(
        self,
        *,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID,
    ) -> AssetModel:
        asset = await self._repository.get_asset(asset_id=asset_id, owner_id=owner_id)
        if asset is None:
            raise AssetNotFound(f"Asset {asset_id} not found")
        return asset

    async def _delete_asset_objects(self, asset: AssetModel) -> None:
        for variant in asset.variants:
            if variant.status == AssetVariantStatusEnum.DELETED:
                continue
            await self._storage.delete_object(
                bucket=variant.storage_bucket,
                key=variant.storage_key,
            )
        await self._repository.mark_asset_deleted(asset_id=asset.asset_id, now=self._now())

    def _dispatch_image_processing(self, asset_id: uuid.UUID) -> None:
        if self._task_dispatcher is None:
            return
        self._task_dispatcher.enqueue_image_processing(asset_id)

    def _dispatch_video_processing(self, asset_id: uuid.UUID) -> None:
        if self._task_dispatcher is None:
            return
        self._task_dispatcher.enqueue_video_processing(asset_id)

    async def _set_video_processing_status(
        self,
        *,
        asset: AssetModel,
        processing_status: VideoProcessingStatusEnum,
        detected_mime_type: str | None,
        metadata: VideoMetadata | None = None,
        available_quality_metadata: dict[str, object] | None = None,
        processing_error: str | None = None,
    ) -> None:
        asset_metadata = dict(asset.asset_metadata or {})
        asset_metadata["video_processing_status"] = processing_status.value
        if detected_mime_type:
            asset_metadata["detected_video_mime_type"] = detected_mime_type
        if metadata is not None:
            asset_metadata["duration_seconds"] = metadata.duration_seconds
            asset_metadata["width"] = metadata.width
            asset_metadata["height"] = metadata.height
            asset_metadata["orientation"] = metadata.orientation.value
            asset_metadata["bitrate"] = metadata.bitrate
        if available_quality_metadata is not None:
            asset_metadata["available_quality_metadata"] = available_quality_metadata
        if processing_error:
            asset_metadata["last_processing_error"] = processing_error
        await self._repository.update_asset_metadata(
            asset_id=asset.asset_id,
            asset_metadata=asset_metadata,
            now=self._now(),
        )
        asset.asset_metadata = asset_metadata
        await self._notify_video_processing(
            AssetVideoProcessingUpdate(
                asset_id=asset.asset_id,
                processing_status=processing_status,
                duration_seconds=metadata.duration_seconds if metadata is not None else None,
                width=metadata.width if metadata is not None else None,
                height=metadata.height if metadata is not None else None,
                orientation=metadata.orientation if metadata is not None else None,
                available_quality_metadata=available_quality_metadata or {},
                processing_error=processing_error,
            )
        )

    async def _notify_video_processing(self, update: AssetVideoProcessingUpdate) -> None:
        if self._video_processing_notifier is None:
            return
        await self._video_processing_notifier.notify(update)

    def _quality_metadata_for_original(
        self,
        *,
        original_variant,
        metadata: VideoMetadata,
    ) -> dict[str, object]:
        return {
            "original": {
                "variant_type": AssetVariantTypeEnum.ORIGINAL.value,
                "width": metadata.width,
                "height": metadata.height,
                "duration_seconds": metadata.duration_seconds,
                "mime_type": original_variant.mime_type,
                "size_bytes": original_variant.size_bytes,
            }
        }

    def _require_avatar_source_asset(self, asset: AssetModel):
        if asset.asset_type != AssetTypeEnum.IMAGE:
            raise InvalidAsset("Avatar asset must be an image")
        if asset.status not in AVATAR_ALLOWED_ASSET_STATUSES:
            raise InvalidAsset(f"Asset {asset.asset_id} is not ready for avatar generation")

        original_variant = next(
            (
                variant
                for variant in asset.variants
                if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL
            ),
            None,
        )
        if original_variant is None or original_variant.status != AssetVariantStatusEnum.READY:
            raise InvalidAsset(f"Asset {asset.asset_id} original image is not available")

        return original_variant

    def _render_variant(
        self,
        *,
        image: Image.Image,
        size: tuple[int, int],
    ) -> RenderedImageVariant:
        variant = image.copy()
        if variant.mode not in ("RGB", "RGBA"):
            variant = variant.convert("RGBA")
        variant.thumbnail(size)
        buffer = io.BytesIO()
        variant.save(buffer, format="WEBP", quality=90)
        return RenderedImageVariant(
            payload=buffer.getvalue(),
            width=variant.width,
            height=variant.height,
        )

    def _render_avatar_variants(
        self,
        payload: bytes,
        crop: AvatarCropSpec,
    ) -> dict[AssetVariantTypeEnum, RenderedImageVariant]:
        image = self._load_image(payload)
        crop_box = self._build_avatar_crop_box(
            image_width=image.width,
            image_height=image.height,
            crop=crop,
        )
        cropped = image.crop(crop_box)

        return {
            variant_type: self._render_avatar_variant(cropped=cropped, size=size)
            for variant_type, size in AVATAR_VARIANTS.items()
        }

    def _render_avatar_variant(
        self,
        *,
        cropped: Image.Image,
        size: tuple[int, int],
    ) -> RenderedImageVariant:
        variant = cropped.copy()
        if variant.mode not in ("RGB", "RGBA"):
            variant = variant.convert("RGBA")
        variant = variant.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        variant.save(buffer, format="WEBP", quality=92)
        return RenderedImageVariant(
            payload=buffer.getvalue(),
            width=variant.width,
            height=variant.height,
        )

    def _build_avatar_crop_box(
        self,
        *,
        image_width: int,
        image_height: int,
        crop: AvatarCropSpec,
    ) -> tuple[int, int, int, int]:
        min_dimension = min(image_width, image_height)
        crop_size_px = int(round(crop.size * min_dimension))
        if crop_size_px < MIN_AVATAR_CROP_SIZE_PX:
            raise InvalidAsset(
                f"Avatar crop is too small; minimum square size is {MIN_AVATAR_CROP_SIZE_PX}px"
            )

        left = int(round(crop.x * image_width))
        top = int(round(crop.y * image_height))
        right = left + crop_size_px
        bottom = top + crop_size_px

        if left < 0 or top < 0 or right > image_width or bottom > image_height:
            raise InvalidAsset("Avatar crop must stay within the source image bounds")

        return left, top, right, bottom

    def _load_image(self, payload: bytes) -> Image.Image:
        image = Image.open(io.BytesIO(payload))
        image.load()
        normalized = ImageOps.exif_transpose(image)
        normalized.load()
        normalized.format = image.format
        return normalized

    def _default_extension(self, asset_type: AssetTypeEnum, mime_type: str | None) -> str:
        guessed_extension = mimetypes.guess_extension(mime_type or "")
        if guessed_extension:
            return guessed_extension.lstrip(".")
        if asset_type == AssetTypeEnum.IMAGE:
            return "img"
        if asset_type == AssetTypeEnum.VIDEO:
            return "mp4"
        return "bin"

    def _is_declared_image(
        self,
        *,
        extension: str | None,
        declared_mime_type: str,
    ) -> bool:
        if declared_mime_type.startswith("image/"):
            return True
        return extension in {"jpg", "jpeg", "png", "gif", "webp"}

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
