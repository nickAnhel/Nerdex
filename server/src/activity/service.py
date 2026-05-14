from __future__ import annotations

import logging
import typing as tp
import uuid

from src.activity.enums import ActivityActionTypeEnum, ActivityPeriodEnum
from src.activity.repository import ActivityRepository
from src.activity.schemas import ActivityCommentPreviewGet, ActivityEventGet, ActivityEventListGet
from src.comments.repository import CommentState
from src.content.access import can_view_content
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.users.presentation import build_user_get
from src.videos.enums import VideoProcessingStatusEnum

if tp.TYPE_CHECKING:
    from src.assets.storage import AssetStorage
    from src.content.projectors import ContentProjectorRegistry


logger = logging.getLogger(__name__)
COMMENT_PREVIEW_MAX_LENGTH = 160


class ActivityService:
    def __init__(
        self,
        repository: ActivityRepository,
        asset_storage: AssetStorage,
        projector_registry: ContentProjectorRegistry,
    ) -> None:
        self._repository = repository
        self._asset_storage = asset_storage
        self._projector_registry = projector_registry

    async def log_content_view(
        self,
        *,
        user_id: uuid.UUID,
        content_id: uuid.UUID,
        content_type: ContentTypeEnum,
        view_session_id: uuid.UUID,
        source: str | None,
        progress_percent: int,
        watched_seconds: int,
        position_seconds: int | None = None,
    ) -> None:
        await self._best_effort_create(
            user_id=user_id,
            action_type=ActivityActionTypeEnum.CONTENT_VIEW,
            content_id=content_id,
            content_type=content_type,
            metadata=self._clean_metadata({
                "view_session_id": str(view_session_id),
                "source": source,
                "progress_percent": progress_percent,
                "watched_seconds": watched_seconds,
                "position_seconds": position_seconds,
            }),
        )

    async def log_content_reaction(
        self,
        *,
        user_id: uuid.UUID,
        content_id: uuid.UUID,
        content_type: ContentTypeEnum,
        previous_reaction: ReactionTypeEnum | None,
        new_reaction: ReactionTypeEnum,
    ) -> None:
        if new_reaction not in {ReactionTypeEnum.LIKE, ReactionTypeEnum.DISLIKE}:
            return

        await self._best_effort_create(
            user_id=user_id,
            action_type=(
                ActivityActionTypeEnum.CONTENT_LIKE
                if new_reaction == ReactionTypeEnum.LIKE
                else ActivityActionTypeEnum.CONTENT_DISLIKE
            ),
            content_id=content_id,
            content_type=content_type,
            metadata=self._clean_metadata({
                "previous_reaction": previous_reaction.value if previous_reaction else None,
                "new_reaction": new_reaction.value,
            }),
        )

    async def log_content_reaction_removed(
        self,
        *,
        user_id: uuid.UUID,
        content_id: uuid.UUID,
        content_type: ContentTypeEnum,
        previous_reaction: ReactionTypeEnum,
    ) -> None:
        await self._best_effort_create(
            user_id=user_id,
            action_type=ActivityActionTypeEnum.CONTENT_REACTION_REMOVED,
            content_id=content_id,
            content_type=content_type,
            metadata={"previous_reaction": previous_reaction.value},
        )

    async def log_content_comment(
        self,
        *,
        user_id: uuid.UUID,
        content_id: uuid.UUID,
        content_type: ContentTypeEnum,
        comment: CommentState,
    ) -> None:
        await self._best_effort_create(
            user_id=user_id,
            action_type=ActivityActionTypeEnum.CONTENT_COMMENT,
            content_id=content_id,
            comment_id=comment.comment_id,
            content_type=content_type,
            metadata=self._clean_metadata({
                "comment_preview": self._preview(comment.body_text),
                "parent_comment_id": str(comment.parent_comment_id) if comment.parent_comment_id else None,
                "root_comment_id": str(comment.root_comment_id) if comment.root_comment_id else None,
                "reply_to_comment_id": str(comment.reply_to_comment_id) if comment.reply_to_comment_id else None,
            }),
        )

    async def log_user_follow(
        self,
        *,
        user_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> None:
        await self._best_effort_create(
            user_id=user_id,
            action_type=ActivityActionTypeEnum.USER_FOLLOW,
            target_user_id=target_user_id,
        )

    async def log_user_unfollow(
        self,
        *,
        user_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> None:
        await self._best_effort_create(
            user_id=user_id,
            action_type=ActivityActionTypeEnum.USER_UNFOLLOW,
            target_user_id=target_user_id,
        )

    async def get_my_activity(
        self,
        *,
        user_id: uuid.UUID,
        action_types: list[ActivityActionTypeEnum] | None,
        content_type: ContentTypeEnum | None,
        period: ActivityPeriodEnum,
        offset: int,
        limit: int,
    ) -> ActivityEventListGet:
        events, has_more = await self._repository.get_user_activity(
            user_id=user_id,
            action_types=action_types,
            content_type=content_type,
            period=period,
            offset=offset,
            limit=limit,
        )
        return ActivityEventListGet(
            items=[await self._build_event_get(event, viewer_id=user_id) for event in events],
            offset=offset,
            limit=limit,
            has_more=has_more,
        )

    async def _best_effort_create(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        try:
            await self._repository.create_event(**kwargs)
        except Exception:
            await self._repository.rollback()
            logger.exception("Failed to write activity event")

    async def _build_event_get(self, event, *, viewer_id: uuid.UUID) -> ActivityEventGet:  # type: ignore[no-untyped-def]
        return ActivityEventGet(
            activity_event_id=event.activity_event_id,
            action_type=event.action_type,
            created_at=event.created_at,
            content_type=event.content_type,
            content=await self._build_content(event.content, viewer_id=viewer_id),
            target_user=(
                await build_user_get(event.target_user, viewer_id=viewer_id, storage=self._asset_storage)
                if event.target_user is not None
                else None
            ),
            comment=self._build_comment_preview(event),
            metadata=self._public_metadata(event),
        )

    async def _build_content(self, content, *, viewer_id: uuid.UUID):  # type: ignore[no-untyped-def]
        if content is None or not self._can_expose_content(content=content, viewer_id=viewer_id):
            return None
        projector = self._projector_registry.get(content.content_type)
        return await projector.project_feed_item(
            content,
            viewer_id=viewer_id,
            storage=self._asset_storage,
        )

    def _can_expose_content(self, *, content, viewer_id: uuid.UUID) -> bool:  # type: ignore[no-untyped-def]
        if not can_view_content(content=content, viewer_id=viewer_id):
            return False
        if content.status != ContentStatusEnum.PUBLISHED:
            return False
        if content.visibility != ContentVisibilityEnum.PUBLIC:
            return False
        if content.content_type in {ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT}:
            return (
                content.video_playback_details is not None
                and content.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
            )
        return True

    def _build_comment_preview(self, event) -> ActivityCommentPreviewGet | None:  # type: ignore[no-untyped-def]
        if event.comment is None and event.comment_id is None:
            return None
        comment = event.comment
        if comment is None:
            return None
        if comment.deleted_at is not None:
            body_preview = None
        else:
            body_preview = self._preview(comment.body_text)
        return ActivityCommentPreviewGet(
            comment_id=comment.comment_id,
            body_preview=body_preview,
            deleted_at=comment.deleted_at,
            created_at=comment.created_at,
        )

    def _public_metadata(self, event) -> dict[str, tp.Any]:  # type: ignore[no-untyped-def]
        metadata = dict(event.event_metadata or {})
        if (
            event.action_type == ActivityActionTypeEnum.CONTENT_COMMENT
            and event.comment is not None
            and event.comment.deleted_at is not None
        ):
            metadata.pop("comment_preview", None)
        return metadata

    def _preview(self, value: str) -> str:
        value = " ".join(value.split())
        if len(value) <= COMMENT_PREVIEW_MAX_LENGTH:
            return value
        return value[: COMMENT_PREVIEW_MAX_LENGTH - 3].rstrip() + "..."

    def _clean_metadata(self, metadata: dict[str, tp.Any]) -> dict[str, tp.Any]:
        return {key: value for key, value in metadata.items() if value is not None}
