from __future__ import annotations

import datetime as dt
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path

from src.assets.enums import AssetAccessTypeEnum, AssetStatusEnum, AssetTypeEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.assets.storage import AssetStorage
from src.demo_seed.media.uploader import upload_bytes_to_s3, upload_path_to_s3
from src.demo_seed.planning.plans import PlannedAsset, PlannedAssetVariant


@dataclass(slots=True)
class ManifestItem:
    seed_run_id: str
    usage_target: str
    topic: str
    provider: str
    provider_item_id: str
    media_type: str
    local_path: str
    s3_key: str
    metadata: dict


class SeedAssetBuilder:
    def __init__(self, storage: AssetStorage, seed_run_id: str) -> None:
        self._storage = storage
        self._seed_run_id = seed_run_id
        self.manifest_items: list[ManifestItem] = []

    async def from_local_file(
        self,
        *,
        owner_id: uuid.UUID,
        local_path: Path,
        key_suffix: str,
        usage_target: str,
        topic: str,
        provider: str,
        provider_item_id: str,
        variant_type: AssetVariantTypeEnum = AssetVariantTypeEnum.ORIGINAL,
        media_type_hint: str | None = None,
        width: int | None = None,
        height: int | None = None,
        duration_ms: int | None = None,
    ) -> PlannedAsset:
        ext = local_path.suffix.lower().lstrip(".") or "bin"
        mime_type = mimetypes.guess_type(local_path.name)[0] or "application/octet-stream"
        if media_type_hint == "image":
            asset_type = AssetTypeEnum.IMAGE
        elif media_type_hint == "video":
            asset_type = AssetTypeEnum.VIDEO
        elif media_type_hint == "file":
            asset_type = AssetTypeEnum.FILE
        else:
            if mime_type.startswith("image/"):
                asset_type = AssetTypeEnum.IMAGE
            elif mime_type.startswith("video/"):
                asset_type = AssetTypeEnum.VIDEO
            else:
                asset_type = AssetTypeEnum.FILE

        s3_key = f"demo/{self._seed_run_id}/{key_suffix}/{local_path.name}"
        stored = await upload_path_to_s3(
            self._storage,
            local_path=local_path,
            key=s3_key,
            mime_type=mime_type,
        )

        now = dt.datetime.now(dt.timezone.utc)
        asset_id = uuid.uuid4()
        variant_id = uuid.uuid4()
        planned = PlannedAsset(
            asset_id=asset_id,
            owner_id=owner_id,
            asset_type=asset_type,
            original_filename=local_path.name,
            original_extension=ext,
            detected_mime_type=mime_type,
            declared_mime_type=mime_type,
            size_bytes=stored.size_bytes,
            status=AssetStatusEnum.READY.value,
            access_type=AssetAccessTypeEnum.PRIVATE.value,
            created_at=now,
            updated_at=now,
            asset_metadata={
                "seed_run_id": self._seed_run_id,
                "usage_target": usage_target,
                "topic": topic,
                "provider": provider,
                "provider_item_id": provider_item_id,
            },
            variants=[
                PlannedAssetVariant(
                    asset_variant_id=variant_id,
                    asset_variant_type=variant_type.value,
                    storage_bucket=self._storage.private_bucket,
                    storage_key=s3_key,
                    mime_type=stored.mime_type,
                    size_bytes=stored.size_bytes,
                    width=width,
                    height=height,
                    duration_ms=duration_ms,
                    bitrate=stored.bitrate,
                    checksum_sha256=stored.checksum_sha256,
                    is_primary=True,
                    status=AssetVariantStatusEnum.READY.value,
                )
            ],
        )

        self.manifest_items.append(
            ManifestItem(
                seed_run_id=self._seed_run_id,
                usage_target=usage_target,
                topic=topic,
                provider=provider,
                provider_item_id=provider_item_id,
                media_type=asset_type.value,
                local_path=str(local_path),
                s3_key=s3_key,
                metadata={"mime_type": mime_type, "width": width, "height": height, "duration_ms": duration_ms},
            )
        )
        return planned

    async def from_bytes(
        self,
        *,
        owner_id: uuid.UUID,
        payload: bytes,
        filename: str,
        mime_type: str,
        key_suffix: str,
        usage_target: str,
        topic: str,
        provider: str,
        provider_item_id: str,
        width: int | None = None,
        height: int | None = None,
        variant_type: AssetVariantTypeEnum = AssetVariantTypeEnum.ORIGINAL,
    ) -> PlannedAsset:
        ext = filename.split(".")[-1].lower() if "." in filename else "bin"
        if mime_type.startswith("image/"):
            asset_type = AssetTypeEnum.IMAGE
        elif mime_type.startswith("video/"):
            asset_type = AssetTypeEnum.VIDEO
        else:
            asset_type = AssetTypeEnum.FILE

        s3_key = f"demo/{self._seed_run_id}/{key_suffix}/{uuid.uuid4()}_{filename}"
        stored = await upload_bytes_to_s3(
            self._storage,
            payload=payload,
            key=s3_key,
            mime_type=mime_type,
        )

        now = dt.datetime.now(dt.timezone.utc)
        asset_id = uuid.uuid4()
        variant_id = uuid.uuid4()
        planned = PlannedAsset(
            asset_id=asset_id,
            owner_id=owner_id,
            asset_type=asset_type,
            original_filename=filename,
            original_extension=ext,
            detected_mime_type=mime_type,
            declared_mime_type=mime_type,
            size_bytes=stored.size_bytes,
            status=AssetStatusEnum.READY.value,
            access_type=AssetAccessTypeEnum.PRIVATE.value,
            created_at=now,
            updated_at=now,
            asset_metadata={
                "seed_run_id": self._seed_run_id,
                "usage_target": usage_target,
                "topic": topic,
                "provider": provider,
                "provider_item_id": provider_item_id,
            },
            variants=[
                PlannedAssetVariant(
                    asset_variant_id=variant_id,
                    asset_variant_type=variant_type.value,
                    storage_bucket=self._storage.private_bucket,
                    storage_key=s3_key,
                    mime_type=mime_type,
                    size_bytes=stored.size_bytes,
                    width=width,
                    height=height,
                    duration_ms=stored.duration_ms,
                    bitrate=stored.bitrate,
                    checksum_sha256=stored.checksum_sha256,
                    is_primary=True,
                    status=AssetVariantStatusEnum.READY.value,
                )
            ],
        )

        self.manifest_items.append(
            ManifestItem(
                seed_run_id=self._seed_run_id,
                usage_target=usage_target,
                topic=topic,
                provider=provider,
                provider_item_id=provider_item_id,
                media_type=asset_type.value,
                local_path="generated",
                s3_key=s3_key,
                metadata={"mime_type": mime_type, "width": width, "height": height},
            )
        )
        return planned
