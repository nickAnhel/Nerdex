from __future__ import annotations

import datetime
import uuid

from src.assets.enums import (
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
    AttachmentTypeEnum,
)
from src.assets.models import AssetModel
from src.assets.repository import AssetRepository
from src.assets.service import AssetService
from src.assets.storage import AssetStorage, detect_extension
from src.common.exceptions import PermissionDenied
from src.content.access import can_view_content
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum
from src.moments.enums import MomentOrder, MomentProfileFilter, MomentWriteStatus, MomentWriteVisibility
from src.moments.exceptions import InvalidMoment, MomentNotFound
from src.moments.presentation import build_moment_editor_get, build_moment_get
from src.moments.repository import MomentRepository
from src.moments.schemas import MomentCreate, MomentEditorGet, MomentGet, MomentUpdate
from src.tags.service import TagService
from src.users.schemas import UserGet
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum


MOMENT_SOURCE_ALLOWED_STATUSES = {
    AssetStatusEnum.UPLOADED,
    AssetStatusEnum.PROCESSING,
    AssetStatusEnum.READY,
}
MOMENT_COVER_ALLOWED_STATUSES = {
    AssetStatusEnum.UPLOADED,
    AssetStatusEnum.PROCESSING,
    AssetStatusEnum.READY,
}
ALLOWED_MOMENT_EXTENSIONS = {"mp4", "webm", "mov"}
ALLOWED_MOMENT_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-quicktime",
}
FORBIDDEN_USAGE_CONTEXTS = {"avatar"}
MAX_MOMENT_DURATION_SECONDS = 90


class MomentService:
    def __init__(
        self,
        repository: MomentRepository,
        tag_service: TagService,
        asset_repository: AssetRepository,
        asset_service: AssetService,
        asset_storage: AssetStorage,
    ) -> None:
        self._repository = repository
        self._tag_service = tag_service
        self._asset_repository = asset_repository
        self._asset_service = asset_service
        self._asset_storage = asset_storage

    async def create_moment(
        self,
        *,
        user: UserGet,
        data: MomentCreate,
    ) -> MomentGet:
        caption = data.caption.strip()
        tags = self._tag_service.normalize_tags(data.tags)
        source_asset, cover_asset = await self._load_and_validate_assets(
            owner_id=user.user_id,
            source_asset_id=data.source_asset_id,
            cover_asset_id=data.cover_asset_id,
        )
        playback_seed = self._build_playback_seed(source_asset)
        self._raise_if_ready_constraints_fail(playback_seed)
        status, published_at, publish_requested_at, processing_error = self._resolve_write_status(
            requested_status=self._map_status(data.status),
            playback_status=playback_seed["processing_status"],
            current_published_at=None,
            current_publish_requested_at=None,
            ready_validation_error=self._ready_publish_validation_error(playback_seed),
        )
        now = self._now()
        moment = await self._repository.create(
            author_id=user.user_id,
            caption=caption,
            excerpt=self._build_excerpt(caption),
            status=status,
            visibility=self._map_visibility(data.visibility),
            duration_seconds=playback_seed["duration_seconds"],
            width=playback_seed["width"],
            height=playback_seed["height"],
            orientation=playback_seed["orientation"],
            processing_status=playback_seed["processing_status"],
            processing_error=processing_error or playback_seed["processing_error"],
            available_quality_metadata=playback_seed["available_quality_metadata"],
            publish_requested_at=publish_requested_at,
            created_at=now,
            updated_at=now,
            published_at=published_at,
            commit=False,
        )
        await self._repository.replace_asset_links(
            content_id=moment.content_id,
            attachments=self._build_attachments(source_asset.asset_id, cover_asset.asset_id),
            commit=False,
        )
        if tags:
            resolved_tags = await self._tag_service.resolve_tags(tags)
            await self._tag_service.replace_content_tags(
                content_id=moment.content_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()
        created = await self._repository.get_single(content_id=moment.content_id, viewer_id=user.user_id)
        if created is None:
            raise MomentNotFound("Created moment is unavailable")
        return await self._build_moment_get(created, viewer_id=user.user_id)

    async def get_feed(
        self,
        *,
        user: UserGet | None,
        offset: int,
        limit: int,
    ) -> list[MomentGet]:
        viewer_id = user.user_id if user else None
        moments = await self._repository.get_feed(viewer_id=viewer_id, offset=offset, limit=limit)
        return [await self._build_moment_get(moment, viewer_id=viewer_id) for moment in moments]

    async def get_moments(
        self,
        *,
        order: MomentOrder,
        desc: bool,
        offset: int,
        limit: int,
        user_id: uuid.UUID | None,
        user: UserGet | None,
        profile_filter: MomentProfileFilter,
    ) -> list[MomentGet]:
        viewer_id = user.user_id if user else None
        if user_id is None:
            moments = await self._repository.get_feed(viewer_id=viewer_id, offset=offset, limit=limit)
        else:
            moments = await self._repository.get_author_moments(
                author_id=user_id,
                viewer_id=viewer_id,
                profile_filter=profile_filter,
                order=order,
                order_desc=desc,
                offset=offset,
                limit=limit,
            )
        return [await self._build_moment_get(moment, viewer_id=viewer_id) for moment in moments]

    async def get_moment(
        self,
        *,
        moment_id: uuid.UUID,
        user: UserGet | None,
    ) -> MomentGet:
        viewer_id = user.user_id if user else None
        moment = await self._repository.get_single(content_id=moment_id, viewer_id=viewer_id)
        if moment is None or not self._can_view_moment(moment=moment, viewer_id=viewer_id):
            raise MomentNotFound(f"Moment with id {moment_id!s} not found")
        return await self._build_moment_get(moment, viewer_id=viewer_id)

    async def get_moment_editor(
        self,
        *,
        moment_id: uuid.UUID,
        user: UserGet,
    ) -> MomentEditorGet:
        moment = await self._repository.get_single(content_id=moment_id, viewer_id=user.user_id)
        if moment is None or moment.author_id != user.user_id or moment.deleted_at is not None:
            raise MomentNotFound(f"Moment with id {moment_id!s} not found")
        return await build_moment_editor_get(moment, viewer_id=user.user_id, storage=self._asset_storage)

    async def update_moment(
        self,
        *,
        user: UserGet,
        moment_id: uuid.UUID,
        data: MomentUpdate,
    ) -> MomentGet:
        moment = await self._repository.get_single(content_id=moment_id, viewer_id=user.user_id)
        if moment is None or moment.author_id != user.user_id:
            raise PermissionDenied(f"User with id {user.user_id} can't edit moment with id {moment_id}")
        if moment.status == ContentStatusEnum.DELETED:
            raise MomentNotFound(f"Moment with id {moment_id!s} not found")

        payload = data.model_dump(exclude_unset=True)
        next_source_asset_id = payload.get("source_asset_id") or self._current_asset_id(moment, AttachmentTypeEnum.VIDEO_SOURCE)
        next_cover_asset_id = payload.get("cover_asset_id") or self._current_asset_id(moment, AttachmentTypeEnum.COVER)
        if next_source_asset_id is None or next_cover_asset_id is None:
            raise InvalidMoment("Moment source and cover assets are required")
        source_asset, cover_asset = await self._load_and_validate_assets(
            owner_id=user.user_id,
            source_asset_id=next_source_asset_id,
            cover_asset_id=next_cover_asset_id,
        )
        next_caption = payload.get("caption", moment.moment_details.caption).strip()
        next_visibility = (
            self._map_visibility(payload["visibility"])
            if "visibility" in payload
            else moment.visibility
        )
        requested_status = (
            self._map_status(payload["status"])
            if "status" in payload
            else moment.status
        )

        playback_status = moment.video_playback_details.processing_status
        ready_validation_error = self._ready_publish_validation_error_from_model(moment)
        if source_asset.asset_id != self._current_asset_id(moment, AttachmentTypeEnum.VIDEO_SOURCE):
            playback_seed = self._build_playback_seed(source_asset)
            self._raise_if_ready_constraints_fail(playback_seed)
            playback_status = playback_seed["processing_status"]
            ready_validation_error = self._ready_publish_validation_error(playback_seed)
            await self._repository.update_playback_details(
                content_id=moment_id,
                duration_seconds=playback_seed["duration_seconds"],
                width=playback_seed["width"],
                height=playback_seed["height"],
                orientation=playback_seed["orientation"],
                processing_status=playback_seed["processing_status"],
                processing_error=playback_seed["processing_error"],
                available_quality_metadata=playback_seed["available_quality_metadata"],
                updated_at=self._now(),
                commit=False,
            )

        next_status, published_at, publish_requested_at, processing_error = self._resolve_write_status(
            requested_status=requested_status,
            playback_status=playback_status,
            current_published_at=moment.published_at,
            current_publish_requested_at=moment.moment_details.publish_requested_at,
            ready_validation_error=ready_validation_error,
        )
        if requested_status == ContentStatusEnum.DRAFT:
            published_at = None

        previous_asset_ids = await self._repository.get_attachment_asset_ids(content_id=moment_id)
        now = self._now()
        await self._repository.update_moment(
            content_id=moment_id,
            caption=next_caption,
            excerpt=self._build_excerpt(next_caption),
            status=next_status,
            visibility=next_visibility,
            publish_requested_at=publish_requested_at,
            updated_at=now,
            published_at=published_at,
            processing_error=processing_error,
            commit=False,
        )
        await self._repository.replace_asset_links(
            content_id=moment_id,
            attachments=self._build_attachments(source_asset.asset_id, cover_asset.asset_id),
            commit=False,
        )
        if data.tags is not None:
            resolved_tags = await self._tag_service.resolve_tags(self._tag_service.normalize_tags(data.tags))
            await self._tag_service.replace_content_tags(
                content_id=moment_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()
        await self._mark_assets_orphaned(
            asset_ids=previous_asset_ids - {source_asset.asset_id, cover_asset.asset_id}
        )
        updated = await self._repository.get_single(content_id=moment_id, viewer_id=user.user_id)
        if updated is None:
            raise MomentNotFound(f"Moment with id {moment_id!s} not found")
        return await self._build_moment_get(updated, viewer_id=user.user_id)

    async def delete_moment(self, *, user: UserGet, moment_id: uuid.UUID) -> None:
        moment = await self._repository.get_single(content_id=moment_id, viewer_id=user.user_id)
        if moment is None or moment.author_id != user.user_id:
            raise PermissionDenied(f"User with id {user.user_id} can't delete moment with id {moment_id}")
        if moment.status == ContentStatusEnum.DELETED:
            return
        attachment_asset_ids = await self._repository.get_attachment_asset_ids(content_id=moment_id)
        now = self._now()
        await self._repository.soft_delete_moment(
            content_id=moment_id,
            updated_at=now,
            deleted_at=now,
            commit=False,
        )
        await self._repository.replace_asset_links(content_id=moment_id, attachments=[], commit=False)
        await self._repository.commit()
        await self._mark_assets_orphaned(asset_ids=attachment_asset_ids)

    async def _load_and_validate_assets(
        self,
        *,
        owner_id: uuid.UUID,
        source_asset_id: uuid.UUID,
        cover_asset_id: uuid.UUID,
    ) -> tuple[AssetModel, AssetModel]:
        assets = await self._asset_repository.get_assets(
            asset_ids=[source_asset_id, cover_asset_id],
            owner_id=owner_id,
        )
        by_id = {asset.asset_id: asset for asset in assets}
        if source_asset_id not in by_id:
            raise InvalidMoment("Moment source asset is unavailable for this user")
        if cover_asset_id not in by_id:
            raise InvalidMoment("Moment cover asset is unavailable for this user")
        source_asset = by_id[source_asset_id]
        cover_asset = by_id[cover_asset_id]
        self._validate_source_asset(source_asset)
        self._validate_cover_asset(cover_asset)
        return source_asset, cover_asset

    def _validate_source_asset(self, asset: AssetModel) -> None:
        if asset.asset_type != AssetTypeEnum.VIDEO:
            raise InvalidMoment("Moment source asset must be a video")
        if asset.status not in MOMENT_SOURCE_ALLOWED_STATUSES:
            raise InvalidMoment("Moment source asset must be finalized before creating moment content")
        if (asset.asset_metadata or {}).get("usage_context") in FORBIDDEN_USAGE_CONTEXTS:
            raise InvalidMoment("Avatar assets cannot be reused as moment sources")
        extension = (asset.original_extension or detect_extension(asset.original_filename or "") or "").lower()
        mime_type = ((asset.detected_mime_type or asset.declared_mime_type or "")).lower()
        if extension not in ALLOWED_MOMENT_EXTENSIONS and mime_type not in ALLOWED_MOMENT_MIME_TYPES:
            raise InvalidMoment("Moment source format must be mp4, webm, or mov")
        original_variant = self._require_original_variant(asset)
        if original_variant.status != AssetVariantStatusEnum.READY:
            raise InvalidMoment("Moment source original file is not available yet")

    def _validate_cover_asset(self, asset: AssetModel) -> None:
        if asset.asset_type != AssetTypeEnum.IMAGE:
            raise InvalidMoment("Moment cover asset must be an image")
        if asset.status not in MOMENT_COVER_ALLOWED_STATUSES:
            raise InvalidMoment("Moment cover asset original image must be uploaded")
        if (asset.asset_metadata or {}).get("usage_context") in FORBIDDEN_USAGE_CONTEXTS:
            raise InvalidMoment("Avatar assets cannot be reused as moment covers")
        original_variant = self._require_original_variant(asset)
        if original_variant.status != AssetVariantStatusEnum.READY:
            raise InvalidMoment("Moment cover original image is not available")

    def _build_playback_seed(self, source_asset: AssetModel) -> dict[str, object]:
        metadata = source_asset.asset_metadata or {}
        processing_status = self._asset_processing_status(source_asset)
        original_variant = self._require_original_variant(source_asset)
        width = metadata.get("width") or original_variant.width
        height = metadata.get("height") or original_variant.height
        duration_seconds = metadata.get("duration_seconds")
        if duration_seconds is None and original_variant.duration_ms is not None:
            duration_seconds = int(original_variant.duration_ms / 1000)
        return {
            "duration_seconds": duration_seconds,
            "width": width,
            "height": height,
            "orientation": self._orientation(width=width, height=height),
            "processing_status": processing_status,
            "processing_error": metadata.get("last_processing_error"),
            "available_quality_metadata": metadata.get("available_quality_metadata") or {},
        }

    def _asset_processing_status(self, asset: AssetModel) -> VideoProcessingStatusEnum:
        raw_status = (asset.asset_metadata or {}).get("video_processing_status")
        if raw_status:
            try:
                return VideoProcessingStatusEnum(raw_status)
            except ValueError:
                pass
        if asset.status == AssetStatusEnum.READY:
            return VideoProcessingStatusEnum.READY
        if asset.status == AssetStatusEnum.UPLOADED:
            return VideoProcessingStatusEnum.UPLOADED
        if asset.status == AssetStatusEnum.PROCESSING:
            return VideoProcessingStatusEnum.TRANSCODING
        return VideoProcessingStatusEnum.PENDING_UPLOAD

    def _resolve_write_status(
        self,
        *,
        requested_status: ContentStatusEnum,
        playback_status: VideoProcessingStatusEnum,
        current_published_at: datetime.datetime | None,
        current_publish_requested_at: datetime.datetime | None,
        ready_validation_error: str | None,
    ) -> tuple[ContentStatusEnum, datetime.datetime | None, datetime.datetime | None, str | None]:
        now = self._now()
        if requested_status == ContentStatusEnum.DRAFT:
            return ContentStatusEnum.DRAFT, current_published_at, None, None
        publish_requested_at = current_publish_requested_at or now
        if playback_status != VideoProcessingStatusEnum.READY:
            return ContentStatusEnum.DRAFT, current_published_at, publish_requested_at, None
        if ready_validation_error is not None:
            return ContentStatusEnum.DRAFT, current_published_at, publish_requested_at, ready_validation_error
        return ContentStatusEnum.PUBLISHED, current_published_at or now, publish_requested_at, None

    def _ready_publish_validation_error(self, playback_seed: dict[str, object]) -> str | None:
        if playback_seed["processing_status"] != VideoProcessingStatusEnum.READY:
            return None
        if playback_seed["orientation"] != VideoOrientationEnum.PORTRAIT:
            return "Publish validation failed: moment source must be portrait"
        duration_seconds = playback_seed["duration_seconds"]
        if duration_seconds is None:
            return "Publish validation failed: moment duration is unavailable"
        if int(duration_seconds) > MAX_MOMENT_DURATION_SECONDS:
            return "Publish validation failed: moment source must be 90 seconds or shorter"
        return None

    def _ready_publish_validation_error_from_model(self, moment) -> str | None:  # type: ignore[no-untyped-def]
        playback = moment.video_playback_details
        if playback is None:
            return "Publish validation failed: source processing is not ready"
        return self._ready_publish_validation_error(
            {
                "processing_status": playback.processing_status,
                "orientation": playback.orientation,
                "duration_seconds": playback.duration_seconds,
            }
        )

    def _raise_if_ready_constraints_fail(self, playback_seed: dict[str, object]) -> None:
        error = self._ready_publish_validation_error(playback_seed)
        if error is not None:
            raise InvalidMoment(error.replace("Publish validation failed: ", ""))

    def _map_status(self, status: MomentWriteStatus | ContentStatusEnum) -> ContentStatusEnum:
        if isinstance(status, ContentStatusEnum):
            return status
        return ContentStatusEnum(status.value)

    def _map_visibility(self, visibility: MomentWriteVisibility | ContentVisibilityEnum) -> ContentVisibilityEnum:
        if isinstance(visibility, ContentVisibilityEnum):
            return visibility
        return ContentVisibilityEnum(visibility.value)

    def _require_original_variant(self, asset: AssetModel):
        original_variant = next(
            (
                variant
                for variant in asset.variants
                if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL
            ),
            None,
        )
        if original_variant is None:
            raise InvalidMoment("Asset original file is missing")
        return original_variant

    def _build_attachments(self, source_asset_id: uuid.UUID, cover_asset_id: uuid.UUID) -> list[dict[str, object]]:
        return [
            {
                "asset_id": source_asset_id,
                "attachment_type": AttachmentTypeEnum.VIDEO_SOURCE,
                "position": 0,
            },
            {
                "asset_id": cover_asset_id,
                "attachment_type": AttachmentTypeEnum.COVER,
                "position": 0,
            },
        ]

    def _current_asset_id(self, moment, attachment_type: AttachmentTypeEnum) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        for link in getattr(moment, "asset_links", []):
            if link.deleted_at is None and link.attachment_type == attachment_type:
                return link.asset_id
        return None

    async def _mark_assets_orphaned(self, *, asset_ids: set[uuid.UUID]) -> None:
        for asset_id in asset_ids:
            await self._asset_service.mark_asset_orphaned_if_unreferenced(asset_id=asset_id)

    async def _build_moment_get(self, moment, *, viewer_id: uuid.UUID | None) -> MomentGet:  # type: ignore[no-untyped-def]
        include_playback_sources = (
            moment.video_playback_details is not None
            and moment.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
            and self._can_view_moment(moment=moment, viewer_id=viewer_id)
        )
        return await build_moment_get(
            moment,
            viewer_id=viewer_id,
            storage=self._asset_storage,
            include_playback_sources=include_playback_sources,
        )

    def _can_view_moment(self, *, moment, viewer_id: uuid.UUID | None) -> bool:  # type: ignore[no-untyped-def]
        if not can_view_content(content=moment, viewer_id=viewer_id):
            return False
        if moment.author_id == viewer_id:
            return True
        return (
            moment.status == ContentStatusEnum.PUBLISHED
            and moment.visibility == ContentVisibilityEnum.PUBLIC
            and moment.video_playback_details is not None
            and moment.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
        )

    def _orientation(self, *, width, height) -> VideoOrientationEnum | None:  # type: ignore[no-untyped-def]
        if width is None or height is None:
            return None
        if width == height:
            return VideoOrientationEnum.SQUARE
        return VideoOrientationEnum.LANDSCAPE if width > height else VideoOrientationEnum.PORTRAIT

    def _build_excerpt(self, caption: str) -> str:
        text = " ".join(caption.split())
        if len(text) <= 220:
            return text
        return text[:217].rstrip() + "..."

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
