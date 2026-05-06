from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

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
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.tags.service import TagService
from src.users.schemas import UserGet
from src.videos.enums import (
    VideoOrder,
    VideoOrientationEnum,
    VideoProcessingStatusEnum,
    VideoProfileFilter,
    VideoWriteStatus,
    VideoWriteVisibility,
)
from src.videos.exceptions import InvalidVideo, VideoNotFound
from src.videos.presentation import build_video_card_get, build_video_editor_get, build_video_get
from src.videos.repository import VideoRepository
from src.videos.schemas import VideoCardGet, VideoCreate, VideoEditorGet, VideoGet, VideoRating, VideoUpdate


VIDEO_SOURCE_ALLOWED_STATUSES = {
    AssetStatusEnum.UPLOADED,
    AssetStatusEnum.PROCESSING,
    AssetStatusEnum.READY,
}
VIDEO_COVER_ALLOWED_STATUSES = {
    AssetStatusEnum.UPLOADED,
    AssetStatusEnum.PROCESSING,
    AssetStatusEnum.READY,
}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
ALLOWED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-quicktime",
}
FORBIDDEN_USAGE_CONTEXTS = {"avatar"}


@dataclass(slots=True)
class VideoProcessingAssetUpdate:
    asset_id: uuid.UUID
    processing_status: VideoProcessingStatusEnum
    duration_seconds: int | None = None
    width: int | None = None
    height: int | None = None
    orientation: VideoOrientationEnum | None = None
    available_quality_metadata: dict[str, object] | None = None
    processing_error: str | None = None


class VideoAssetProcessingNotifier:
    def __init__(self, repository: VideoRepository) -> None:
        self._repository = repository

    async def notify(self, update: VideoProcessingAssetUpdate) -> None:
        await self._repository.update_processing_for_source_asset(
            asset_id=update.asset_id,
            processing_status=update.processing_status,
            duration_seconds=update.duration_seconds,
            width=update.width,
            height=update.height,
            orientation=update.orientation,
            available_quality_metadata=update.available_quality_metadata or {},
            processing_error=update.processing_error,
            now=datetime.datetime.now(datetime.timezone.utc),
        )


class VideoService:
    def __init__(
        self,
        repository: VideoRepository,
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

    async def create_video(
        self,
        *,
        user: UserGet,
        data: VideoCreate,
    ) -> VideoGet:
        title = data.title.strip()
        description = data.description.strip()
        tags = self._tag_service.normalize_tags(data.tags)
        source_asset, cover_asset = await self._load_and_validate_assets(
            owner_id=user.user_id,
            source_asset_id=data.source_asset_id,
            cover_asset_id=data.cover_asset_id,
        )
        playback_seed = self._build_playback_seed(source_asset)
        status, published_at, publish_requested_at, processing_error = self._resolve_write_status(
            requested_status=self._map_status(data.status),
            title=title,
            playback_status=playback_seed["processing_status"],
            current_published_at=None,
            current_publish_requested_at=None,
        )
        now = self._now()
        video = await self._repository.create(
            author_id=user.user_id,
            title=title,
            excerpt=self._build_excerpt(description),
            description=description,
            chapters=[chapter.model_dump() for chapter in data.chapters],
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
            content_id=video.content_id,
            attachments=self._build_attachments(source_asset.asset_id, cover_asset.asset_id),
            commit=False,
        )
        if tags:
            resolved_tags = await self._tag_service.resolve_tags(tags)
            await self._tag_service.replace_content_tags(
                content_id=video.content_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()
        created = await self._repository.get_single(content_id=video.content_id, viewer_id=user.user_id)
        if created is None:
            raise VideoNotFound("Created video is unavailable")
        return await self._build_video_get(created, viewer_id=user.user_id)

    async def get_video(
        self,
        *,
        video_id: uuid.UUID,
        user: UserGet | None,
    ) -> VideoGet:
        viewer_id = user.user_id if user else None
        video = await self._repository.get_single(content_id=video_id, viewer_id=viewer_id)
        if video is None or not self._can_view_video(video=video, viewer_id=viewer_id):
            raise VideoNotFound(f"Video with id {video_id!s} not found")
        return await self._build_video_get(video, viewer_id=viewer_id)

    async def get_video_editor(
        self,
        *,
        video_id: uuid.UUID,
        user: UserGet,
    ) -> VideoEditorGet:
        video = await self._repository.get_single(content_id=video_id, viewer_id=user.user_id)
        if video is None or video.author_id != user.user_id or video.deleted_at is not None:
            raise VideoNotFound(f"Video with id {video_id!s} not found")
        return await build_video_editor_get(video, viewer_id=user.user_id, storage=self._asset_storage)

    async def get_videos(
        self,
        *,
        order: VideoOrder,
        desc: bool,
        offset: int,
        limit: int,
        user_id: uuid.UUID | None,
        user: UserGet | None,
        profile_filter: VideoProfileFilter,
    ) -> list[VideoCardGet]:
        viewer_id = user.user_id if user else None
        if user_id is None:
            videos = await self._repository.get_feed(
                viewer_id=viewer_id,
                order=order,
                order_desc=desc,
                offset=offset,
                limit=limit,
            )
        else:
            videos = await self._repository.get_author_videos(
                author_id=user_id,
                viewer_id=viewer_id,
                profile_filter=profile_filter,
                order=order,
                order_desc=desc,
                offset=offset,
                limit=limit,
            )
        return [
            await build_video_card_get(video, viewer_id=viewer_id, storage=self._asset_storage)
            for video in videos
        ]

    async def update_video(
        self,
        *,
        user: UserGet,
        video_id: uuid.UUID,
        data: VideoUpdate,
    ) -> VideoGet:
        video = await self._repository.get_single(content_id=video_id, viewer_id=user.user_id)
        if video is None or video.author_id != user.user_id:
            raise PermissionDenied(f"User with id {user.user_id} can't edit video with id {video_id}")
        if video.status == ContentStatusEnum.DELETED:
            raise VideoNotFound(f"Video with id {video_id!s} not found")

        payload = data.model_dump(exclude_unset=True)
        next_source_asset_id = payload.get("source_asset_id") or self._current_asset_id(video, AttachmentTypeEnum.VIDEO_SOURCE)
        next_cover_asset_id = payload.get("cover_asset_id") or self._current_asset_id(video, AttachmentTypeEnum.COVER)
        if next_source_asset_id is None or next_cover_asset_id is None:
            raise InvalidVideo("Video source and cover assets are required")
        source_asset, cover_asset = await self._load_and_validate_assets(
            owner_id=user.user_id,
            source_asset_id=next_source_asset_id,
            cover_asset_id=next_cover_asset_id,
        )
        next_title = payload.get("title", video.title or "").strip()
        next_description = payload.get("description", video.video_details.description).strip()
        next_chapters = (
            [chapter.model_dump() for chapter in data.chapters]
            if data.chapters is not None
            else video.video_details.chapters
        )
        next_visibility = (
            self._map_visibility(payload["visibility"])
            if "visibility" in payload
            else video.visibility
        )
        requested_status = (
            self._map_status(payload["status"])
            if "status" in payload
            else video.status
        )
        playback_status = video.video_playback_details.processing_status
        if source_asset.asset_id != self._current_asset_id(video, AttachmentTypeEnum.VIDEO_SOURCE):
            playback_seed = self._build_playback_seed(source_asset)
            playback_status = playback_seed["processing_status"]
            await self._repository.update_playback_details(
                content_id=video_id,
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
            title=next_title,
            playback_status=playback_status,
            current_published_at=video.published_at,
            current_publish_requested_at=video.video_details.publish_requested_at,
        )
        if requested_status == ContentStatusEnum.DRAFT:
            published_at = None

        previous_asset_ids = await self._repository.get_attachment_asset_ids(content_id=video_id)
        now = self._now()
        await self._repository.update_video(
            content_id=video_id,
            title=next_title,
            excerpt=self._build_excerpt(next_description),
            description=next_description,
            chapters=next_chapters,
            status=next_status,
            visibility=next_visibility,
            publish_requested_at=publish_requested_at,
            updated_at=now,
            published_at=published_at,
            processing_error=processing_error,
            commit=False,
        )
        await self._repository.replace_asset_links(
            content_id=video_id,
            attachments=self._build_attachments(source_asset.asset_id, cover_asset.asset_id),
            commit=False,
        )
        if data.tags is not None:
            resolved_tags = await self._tag_service.resolve_tags(self._tag_service.normalize_tags(data.tags))
            await self._tag_service.replace_content_tags(
                content_id=video_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()
        await self._mark_assets_orphaned(
            asset_ids=previous_asset_ids - {source_asset.asset_id, cover_asset.asset_id}
        )
        updated = await self._repository.get_single(content_id=video_id, viewer_id=user.user_id)
        if updated is None:
            raise VideoNotFound(f"Video with id {video_id!s} not found")
        return await self._build_video_get(updated, viewer_id=user.user_id)

    async def delete_video(self, *, user: UserGet, video_id: uuid.UUID) -> None:
        video = await self._repository.get_single(content_id=video_id, viewer_id=user.user_id)
        if video is None or video.author_id != user.user_id:
            raise PermissionDenied(f"User with id {user.user_id} can't delete video with id {video_id}")
        if video.status == ContentStatusEnum.DELETED:
            return
        attachment_asset_ids = await self._repository.get_attachment_asset_ids(content_id=video_id)
        now = self._now()
        await self._repository.soft_delete_video(
            content_id=video_id,
            updated_at=now,
            deleted_at=now,
            commit=False,
        )
        await self._repository.replace_asset_links(content_id=video_id, attachments=[], commit=False)
        await self._repository.commit()
        await self._mark_assets_orphaned(asset_ids=attachment_asset_ids)

    async def add_like_to_video(self, *, video_id: uuid.UUID, user_id: uuid.UUID) -> VideoRating:
        await self._get_reactable_video(video_id=video_id, viewer_id=user_id)
        await self._repository.set_reaction(content_id=video_id, user_id=user_id, reaction_type=ReactionTypeEnum.LIKE)
        return await self._build_rating(video_id=video_id, viewer_id=user_id)

    async def remove_like_from_video(self, *, video_id: uuid.UUID, user_id: uuid.UUID) -> VideoRating:
        await self._get_reactable_video(video_id=video_id, viewer_id=user_id)
        await self._repository.remove_reaction(content_id=video_id, user_id=user_id, reaction_type=ReactionTypeEnum.LIKE)
        return await self._build_rating(video_id=video_id, viewer_id=user_id)

    async def add_dislike_to_video(self, *, video_id: uuid.UUID, user_id: uuid.UUID) -> VideoRating:
        await self._get_reactable_video(video_id=video_id, viewer_id=user_id)
        await self._repository.set_reaction(content_id=video_id, user_id=user_id, reaction_type=ReactionTypeEnum.DISLIKE)
        return await self._build_rating(video_id=video_id, viewer_id=user_id)

    async def remove_dislike_from_video(self, *, video_id: uuid.UUID, user_id: uuid.UUID) -> VideoRating:
        await self._get_reactable_video(video_id=video_id, viewer_id=user_id)
        await self._repository.remove_reaction(content_id=video_id, user_id=user_id, reaction_type=ReactionTypeEnum.DISLIKE)
        return await self._build_rating(video_id=video_id, viewer_id=user_id)

    async def _build_rating(self, *, video_id: uuid.UUID, viewer_id: uuid.UUID) -> VideoRating:
        video = await self._repository.get_single(content_id=video_id, viewer_id=viewer_id)
        if video is None:
            raise VideoNotFound(f"Video with id {video_id!s} not found")
        return VideoRating(
            video_id=video.content_id,
            likes_count=video.likes_count,
            dislikes_count=video.dislikes_count,
            my_reaction=video.my_reaction,
        )

    async def _get_reactable_video(self, *, video_id: uuid.UUID, viewer_id: uuid.UUID):
        video = await self._repository.get_single(content_id=video_id, viewer_id=viewer_id)
        if video is None or not self._can_view_video(video=video, viewer_id=viewer_id):
            raise VideoNotFound(f"Video with id {video_id!s} not found")
        if (
            video.status != ContentStatusEnum.PUBLISHED
            or video.video_playback_details.processing_status != VideoProcessingStatusEnum.READY
        ):
            raise VideoNotFound(f"Video with id {video_id!s} not found")
        return video

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
            raise InvalidVideo("Video source asset is unavailable for this user")
        if cover_asset_id not in by_id:
            raise InvalidVideo("Video cover asset is unavailable for this user")
        source_asset = by_id[source_asset_id]
        cover_asset = by_id[cover_asset_id]
        self._validate_source_asset(source_asset)
        self._validate_cover_asset(cover_asset)
        return source_asset, cover_asset

    def _validate_source_asset(self, asset: AssetModel) -> None:
        if asset.asset_type != AssetTypeEnum.VIDEO:
            raise InvalidVideo("Video source asset must be a video")
        if asset.status not in VIDEO_SOURCE_ALLOWED_STATUSES:
            raise InvalidVideo("Video source asset must be finalized before creating video content")
        if asset.size_bytes is not None and asset.size_bytes > 250 * 1024 * 1024:
            raise InvalidVideo("Video source asset exceeds 250 MB")
        if (asset.asset_metadata or {}).get("usage_context") in FORBIDDEN_USAGE_CONTEXTS:
            raise InvalidVideo("Avatar assets cannot be reused as video sources")
        extension = (asset.original_extension or detect_extension(asset.original_filename or "") or "").lower()
        mime_type = ((asset.detected_mime_type or asset.declared_mime_type or "")).lower()
        if extension not in ALLOWED_VIDEO_EXTENSIONS and mime_type not in ALLOWED_VIDEO_MIME_TYPES:
            raise InvalidVideo("Video source format must be mp4, webm, or mov")
        original_variant = self._require_original_variant(asset)
        if original_variant.status != AssetVariantStatusEnum.READY:
            raise InvalidVideo("Video source original file is not available yet")

    def _validate_cover_asset(self, asset: AssetModel) -> None:
        if asset.asset_type != AssetTypeEnum.IMAGE:
            raise InvalidVideo("Video cover asset must be an image")
        if asset.status not in VIDEO_COVER_ALLOWED_STATUSES:
            raise InvalidVideo("Video cover asset original image must be uploaded")
        if (asset.asset_metadata or {}).get("usage_context") in FORBIDDEN_USAGE_CONTEXTS:
            raise InvalidVideo("Avatar assets cannot be reused as video covers")
        original_variant = self._require_original_variant(asset)
        if original_variant.status != AssetVariantStatusEnum.READY:
            raise InvalidVideo("Video cover original image is not available")

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
        title: str,
        playback_status: VideoProcessingStatusEnum,
        current_published_at: datetime.datetime | None,
        current_publish_requested_at: datetime.datetime | None,
    ) -> tuple[ContentStatusEnum, datetime.datetime | None, datetime.datetime | None, str | None]:
        now = self._now()
        if requested_status == ContentStatusEnum.DRAFT:
            return ContentStatusEnum.DRAFT, current_published_at, None, None
        publish_requested_at = current_publish_requested_at or now
        if playback_status != VideoProcessingStatusEnum.READY:
            return ContentStatusEnum.DRAFT, current_published_at, publish_requested_at, None
        if not title:
            return (
                ContentStatusEnum.DRAFT,
                current_published_at,
                publish_requested_at,
                "Publish validation failed: title is required",
            )
        return ContentStatusEnum.PUBLISHED, current_published_at or now, publish_requested_at, None

    def _map_status(self, status: VideoWriteStatus | ContentStatusEnum) -> ContentStatusEnum:
        if isinstance(status, ContentStatusEnum):
            return status
        return ContentStatusEnum(status.value)

    def _map_visibility(self, visibility: VideoWriteVisibility | ContentVisibilityEnum) -> ContentVisibilityEnum:
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
            raise InvalidVideo("Asset original file is missing")
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

    def _current_asset_id(self, video, attachment_type: AttachmentTypeEnum) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        for link in getattr(video, "asset_links", []):
            if link.deleted_at is None and link.attachment_type == attachment_type:
                return link.asset_id
        return None

    async def _mark_assets_orphaned(self, *, asset_ids: set[uuid.UUID]) -> None:
        for asset_id in asset_ids:
            await self._asset_service.mark_asset_orphaned_if_unreferenced(asset_id=asset_id)

    async def _build_video_get(self, video, *, viewer_id: uuid.UUID | None) -> VideoGet:  # type: ignore[no-untyped-def]
        include_playback_sources = (
            video.video_playback_details is not None
            and video.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
            and self._can_view_video(video=video, viewer_id=viewer_id)
        )
        if viewer_id is not None and hasattr(self._repository, "get_latest_view_session"):
            latest_session = await self._repository.get_latest_view_session(
                content_id=video.content_id,
                viewer_id=viewer_id,
            )
            video.history_progress = (
                {
                    "last_position_seconds": latest_session.last_position_seconds,
                    "max_position_seconds": latest_session.max_position_seconds,
                    "watched_seconds": latest_session.watched_seconds,
                    "progress_percent": latest_session.progress_percent,
                    "last_seen_at": latest_session.last_seen_at,
                }
                if latest_session is not None
                else None
            )
        return await build_video_get(
            video,
            viewer_id=viewer_id,
            storage=self._asset_storage,
            include_playback_sources=include_playback_sources,
        )

    def _can_view_video(self, *, video, viewer_id: uuid.UUID | None) -> bool:  # type: ignore[no-untyped-def]
        return can_view_content(content=video, viewer_id=viewer_id)

    def _orientation(self, *, width, height) -> VideoOrientationEnum | None:  # type: ignore[no-untyped-def]
        if width is None or height is None:
            return None
        if width == height:
            return VideoOrientationEnum.SQUARE
        return VideoOrientationEnum.LANDSCAPE if width > height else VideoOrientationEnum.PORTRAIT

    def _build_excerpt(self, description: str) -> str:
        text = " ".join(description.split())
        if len(text) <= 220:
            return text
        return text[:217].rstrip() + "..."

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
