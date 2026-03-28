from __future__ import annotations

import datetime
import typing as tp
import uuid

from sqlalchemy import Select, and_, exists, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.enums import (
    AssetAccessTypeEnum,
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
)
from src.assets.models import AssetModel, AssetVariantModel, ContentAssetModel, MessageAssetModel
from src.users.models import UserModel


class AssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_upload(
        self,
        *,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID,
        asset_type: AssetTypeEnum,
        original_filename: str,
        original_extension: str | None,
        declared_mime_type: str | None,
        access_type: AssetAccessTypeEnum,
        asset_metadata: dict[str, tp.Any],
        storage_bucket: str,
        storage_key: str,
        original_mime_type: str,
        now: datetime.datetime,
    ) -> AssetModel:
        asset_stmt = (
            insert(AssetModel)
            .values(
                asset_id=asset_id,
                owner_id=owner_id,
                asset_type=asset_type,
                original_filename=original_filename,
                original_extension=original_extension,
                declared_mime_type=declared_mime_type,
                status=AssetStatusEnum.PENDING_UPLOAD,
                access_type=access_type,
                asset_metadata=asset_metadata,
                created_at=now,
                updated_at=now,
            )
        )
        await self._session.execute(asset_stmt)

        await self._session.execute(
            insert(AssetVariantModel).values(
                asset_id=asset_id,
                asset_variant_type=AssetVariantTypeEnum.ORIGINAL,
                storage_bucket=storage_bucket,
                storage_key=storage_key,
                mime_type=original_mime_type,
                size_bytes=0,
                is_primary=True,
                status=AssetVariantStatusEnum.PENDING,
            )
        )
        await self._session.commit()
        return await self.get_asset(asset_id=asset_id)

    async def get_asset(
        self,
        *,
        asset_id: uuid.UUID,
        owner_id: uuid.UUID | None = None,
    ) -> AssetModel | None:
        stmt = self._asset_query().where(AssetModel.asset_id == asset_id)
        if owner_id is not None:
            stmt = stmt.where(AssetModel.owner_id == owner_id)

        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_original_variant(
        self,
        *,
        asset_id: uuid.UUID,
    ) -> AssetVariantModel | None:
        stmt = select(AssetVariantModel).where(
            AssetVariantModel.asset_id == asset_id,
            AssetVariantModel.asset_variant_type == AssetVariantTypeEnum.ORIGINAL,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_after_finalize(
        self,
        *,
        asset_id: uuid.UUID,
        size_bytes: int,
        original_mime_type: str,
        status: AssetStatusEnum,
        now: datetime.datetime,
    ) -> AssetModel:
        await self._session.execute(
            update(AssetModel)
            .where(AssetModel.asset_id == asset_id)
            .values(
                size_bytes=size_bytes,
                status=status,
                updated_at=now,
            )
        )
        await self._session.execute(
            update(AssetVariantModel)
            .where(AssetVariantModel.asset_id == asset_id)
            .where(AssetVariantModel.asset_variant_type == AssetVariantTypeEnum.ORIGINAL)
            .values(
                size_bytes=size_bytes,
                mime_type=original_mime_type,
                status=AssetVariantStatusEnum.READY,
            )
        )
        await self._session.commit()
        asset = await self.get_asset(asset_id=asset_id)
        assert asset is not None
        return asset

    async def set_asset_processing(
        self,
        *,
        asset_id: uuid.UUID,
        now: datetime.datetime,
    ) -> None:
        await self._session.execute(
            update(AssetModel)
            .where(AssetModel.asset_id == asset_id)
            .values(status=AssetStatusEnum.PROCESSING, updated_at=now)
        )
        await self._session.commit()

    async def set_asset_ready(
        self,
        *,
        asset_id: uuid.UUID,
        detected_mime_type: str | None,
        now: datetime.datetime,
    ) -> None:
        await self._session.execute(
            update(AssetModel)
            .where(AssetModel.asset_id == asset_id)
            .values(
                status=AssetStatusEnum.READY,
                detected_mime_type=detected_mime_type,
                updated_at=now,
            )
        )
        await self._session.commit()

    async def set_asset_failed(
        self,
        *,
        asset_id: uuid.UUID,
        error_message: str,
        now: datetime.datetime,
    ) -> None:
        asset = await self.get_asset(asset_id=asset_id)
        if asset is None:
            return

        metadata = dict(asset.asset_metadata)
        metadata["last_processing_error"] = error_message
        await self._session.execute(
            update(AssetModel)
            .where(AssetModel.asset_id == asset_id)
            .values(
                status=AssetStatusEnum.FAILED,
                asset_metadata=metadata,
                updated_at=now,
            )
        )
        await self._session.execute(
            update(AssetVariantModel)
            .where(AssetVariantModel.asset_id == asset_id)
            .where(AssetVariantModel.asset_variant_type != AssetVariantTypeEnum.ORIGINAL)
            .values(status=AssetVariantStatusEnum.FAILED)
        )
        await self._session.commit()

    async def upsert_variant(
        self,
        *,
        asset_id: uuid.UUID,
        asset_variant_type: AssetVariantTypeEnum,
        storage_bucket: str,
        storage_key: str,
        mime_type: str,
        size_bytes: int,
        width: int | None,
        height: int | None,
        duration_ms: int | None,
        bitrate: int | None,
        checksum_sha256: str | None,
        is_primary: bool,
        status: AssetVariantStatusEnum,
        variant_metadata: dict[str, tp.Any] | None = None,
    ) -> None:
        existing = await self._get_variant(asset_id=asset_id, asset_variant_type=asset_variant_type)
        values = {
            "storage_bucket": storage_bucket,
            "storage_key": storage_key,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "width": width,
            "height": height,
            "duration_ms": duration_ms,
            "bitrate": bitrate,
            "checksum_sha256": checksum_sha256,
            "is_primary": is_primary,
            "status": status,
            "variant_metadata": variant_metadata or {},
        }
        if existing is None:
            await self._session.execute(
                insert(AssetVariantModel).values(
                    asset_id=asset_id,
                    asset_variant_type=asset_variant_type,
                    **values,
                )
            )
        else:
            await self._session.execute(
                update(AssetVariantModel)
                .where(AssetVariantModel.asset_variant_id == existing.asset_variant_id)
                .values(**values)
            )
        await self._session.commit()

    async def mark_asset_deleted(
        self,
        *,
        asset_id: uuid.UUID,
        now: datetime.datetime,
    ) -> None:
        await self._session.execute(
            update(AssetModel)
            .where(AssetModel.asset_id == asset_id)
            .values(
                status=AssetStatusEnum.DELETED,
                deleted_at=now,
                updated_at=now,
            )
        )
        await self._session.execute(
            update(AssetVariantModel)
            .where(AssetVariantModel.asset_id == asset_id)
            .values(status=AssetVariantStatusEnum.DELETED)
        )
        await self._session.commit()

    async def update_asset_metadata(
        self,
        *,
        asset_id: uuid.UUID,
        asset_metadata: dict[str, tp.Any],
        now: datetime.datetime | None = None,
    ) -> None:
        values: dict[str, tp.Any] = {"asset_metadata": asset_metadata}
        if now is not None:
            values["updated_at"] = now
        await self._session.execute(
            update(AssetModel)
            .where(AssetModel.asset_id == asset_id)
            .values(**values)
        )
        await self._session.commit()

    async def get_stale_pending_uploads(
        self,
        *,
        created_before: datetime.datetime,
    ) -> list[AssetModel]:
        stmt = (
            self._asset_query()
            .where(AssetModel.status == AssetStatusEnum.PENDING_UPLOAD)
            .where(AssetModel.created_at <= created_before)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_orphaned_assets(
        self,
        *,
        orphaned_before: datetime.datetime,
    ) -> list[AssetModel]:
        stmt = (
            self._asset_query()
            .where(AssetModel.status.in_([AssetStatusEnum.READY, AssetStatusEnum.FAILED]))
            .where(AssetModel.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        assets = list(result.scalars().all())
        return [
            asset
            for asset in assets
            if asset.asset_metadata.get("orphaned_at")
            and datetime.datetime.fromisoformat(asset.asset_metadata["orphaned_at"]) <= orphaned_before
        ]

    async def get_failed_assets(
        self,
        *,
        updated_before: datetime.datetime,
    ) -> list[AssetModel]:
        stmt = (
            self._asset_query()
            .where(AssetModel.status == AssetStatusEnum.FAILED)
            .where(AssetModel.updated_at <= updated_before)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def asset_has_active_links(
        self,
        *,
        asset_id: uuid.UUID,
    ) -> bool:
        content_exists = await self._session.scalar(
            select(
                exists().where(
                    and_(
                        ContentAssetModel.asset_id == asset_id,
                        ContentAssetModel.deleted_at.is_(None),
                    )
                )
            )
        )
        if content_exists:
            return True

        message_exists = await self._session.scalar(
            select(
                exists().where(
                    and_(
                        MessageAssetModel.asset_id == asset_id,
                        MessageAssetModel.deleted_at.is_(None),
                    )
                )
            )
        )
        if message_exists:
            return True

        avatar_exists = await self._session.scalar(
            select(exists().where(UserModel.avatar_asset_id == asset_id))
        )
        return bool(avatar_exists)

    async def mark_orphaned(
        self,
        *,
        asset_id: uuid.UUID,
        orphaned_at: str,
        now: datetime.datetime,
    ) -> None:
        asset = await self.get_asset(asset_id=asset_id)
        if asset is None:
            return

        metadata = dict(asset.asset_metadata)
        metadata["orphaned_at"] = orphaned_at
        await self.update_asset_metadata(asset_id=asset_id, asset_metadata=metadata, now=now)

    async def _get_variant(
        self,
        *,
        asset_id: uuid.UUID,
        asset_variant_type: AssetVariantTypeEnum,
    ) -> AssetVariantModel | None:
        stmt = select(AssetVariantModel).where(
            AssetVariantModel.asset_id == asset_id,
            AssetVariantModel.asset_variant_type == asset_variant_type,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    def _asset_query(self) -> Select[tuple[AssetModel]]:
        return select(AssetModel).options(selectinload(AssetModel.variants))
