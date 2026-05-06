from __future__ import annotations

import datetime
import math
import uuid

from src.assets.storage import AssetStorage
from src.content.access import can_view_content
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ReactionTypeEnum
from src.content.enums_list import ContentOrder
from src.content.exceptions import ContentNotFound, InvalidContentAction
from src.content.projectors import ContentProjectorRegistry
from src.content.repository import ContentRepository
from src.content.schemas import (
    ContentHistoryItemGet,
    ContentHistoryProgressGet,
    ContentListItemGet,
    ContentReactionGet,
    ContentViewSessionGet,
    ContentViewSessionHeartbeat,
    ContentViewSessionStart,
)
from src.users.schemas import UserGet
from src.videos.enums import VideoProcessingStatusEnum


class ContentService:
    def __init__(
        self,
        repository: ContentRepository,
        asset_storage: AssetStorage,
        projector_registry: ContentProjectorRegistry,
    ) -> None:
        self._repository = repository
        self._asset_storage = asset_storage
        self._projector_registry = projector_registry

    async def get_feed(
        self,
        *,
        order: ContentOrder,
        desc: bool,
        offset: int,
        limit: int,
        viewer_id: uuid.UUID | None,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_feed(
            viewer_id=viewer_id,
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=viewer_id) for item in content_items]

    async def get_subscriptions_feed(
        self,
        *,
        user_id: uuid.UUID,
        order: ContentOrder,
        desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_user_subscriptions_feed(
            user_id=user_id,
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=user_id) for item in content_items]

    async def get_video_recommendations(
        self,
        *,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_video_recommendations(
            viewer_id=viewer_id,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=viewer_id) for item in content_items]

    async def get_video_subscriptions(
        self,
        *,
        user_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_video_subscriptions(
            user_id=user_id,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=user_id) for item in content_items]

    async def set_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user: UserGet,
        reaction_type: ReactionTypeEnum,
    ) -> ContentReactionGet:
        await self._get_reactable_content(content_id=content_id, viewer_id=user.user_id)
        await self._repository.set_reaction(
            content_id=content_id,
            user_id=user.user_id,
            reaction_type=reaction_type,
        )
        return await self._build_reaction_get(content_id=content_id, viewer_id=user.user_id)

    async def remove_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user: UserGet,
        reaction_type: ReactionTypeEnum | None = None,
    ) -> ContentReactionGet:
        await self._get_reactable_content(content_id=content_id, viewer_id=user.user_id)
        await self._repository.remove_reaction(
            content_id=content_id,
            user_id=user.user_id,
            reaction_type=reaction_type,
        )
        return await self._build_reaction_get(content_id=content_id, viewer_id=user.user_id)

    async def start_view_session(
        self,
        *,
        content_id: uuid.UUID,
        user: UserGet,
        data: ContentViewSessionStart,
    ) -> ContentViewSessionGet:
        content = await self._get_viewable_playback_content(content_id=content_id, viewer_id=user.user_id)
        duration_seconds = self._content_duration_seconds(content)
        position = self._bounded_position(data.initial_position_seconds or 0, duration_seconds)
        now = self._now()
        latest = await self._repository.get_latest_view_session(
            content_id=content_id,
            viewer_id=user.user_id,
        )
        session = await self._repository.create_view_session(
            content_id=content_id,
            viewer_id=user.user_id,
            started_at=now,
            position_seconds=position,
            progress_percent=self._progress_percent(position, duration_seconds),
            source=data.source,
            metadata=data.metadata,
        )
        if latest is not None:
            session.last_position_seconds = latest.last_position_seconds
            session.max_position_seconds = latest.max_position_seconds
            session.watched_seconds = latest.watched_seconds
            session.progress_percent = latest.progress_percent
            session.last_seen_at = latest.last_seen_at
        return self._build_view_session_get(session, views_count=content.views_count)

    async def heartbeat_view_session(
        self,
        *,
        content_id: uuid.UUID,
        session_id: uuid.UUID,
        user: UserGet,
        data: ContentViewSessionHeartbeat,
    ) -> ContentViewSessionGet:
        return await self._update_view_session(
            content_id=content_id,
            session_id=session_id,
            user=user,
            data=data,
        )

    async def finish_view_session(
        self,
        *,
        content_id: uuid.UUID,
        session_id: uuid.UUID,
        user: UserGet,
        data: ContentViewSessionHeartbeat,
    ) -> ContentViewSessionGet:
        data.ended = True
        return await self._update_view_session(
            content_id=content_id,
            session_id=session_id,
            user=user,
            data=data,
        )

    async def get_history(
        self,
        *,
        user: UserGet,
        content_type: ContentTypeEnum | None = None,
        offset: int,
        limit: int,
    ) -> list[ContentHistoryItemGet]:
        rows = await self._repository.get_history_sessions(
            viewer_id=user.user_id,
            content_type=content_type,
            offset=offset,
            limit=limit,
        )
        return [
            ContentHistoryItemGet(
                content=await self._build_feed_item(item, viewer_id=user.user_id),
                progress=self._build_history_progress_get(session),
            )
            for item, session in rows
        ]

    async def _build_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
    ) -> ContentListItemGet:
        projector = self._projector_registry.get(item.content_type)
        return await projector.project_feed_item(
            item,
            viewer_id=viewer_id,
            storage=self._asset_storage,
        )

    async def _build_reaction_get(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> ContentReactionGet:
        content = await self._repository.get_single(content_id=content_id, viewer_id=viewer_id)
        if content is None:
            raise ContentNotFound(f"Content with id {content_id!s} not found")
        return ContentReactionGet(
            content_id=content.content_id,
            likes_count=content.likes_count,
            dislikes_count=content.dislikes_count,
            my_reaction=content.my_reaction,
        )

    async def _get_reactable_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        content = await self._repository.get_single(content_id=content_id, viewer_id=viewer_id)
        if content is None or not can_view_content(content=content, viewer_id=viewer_id):
            raise ContentNotFound(f"Content with id {content_id!s} not found")
        if content.status != ContentStatusEnum.PUBLISHED:
            raise ContentNotFound(f"Content with id {content_id!s} not found")
        if (
            content.content_type == ContentTypeEnum.VIDEO
            and (
                content.video_playback_details is None
                or content.video_playback_details.processing_status != VideoProcessingStatusEnum.READY
            )
        ):
            raise ContentNotFound(f"Content with id {content_id!s} not found")
        return content

    async def _get_viewable_playback_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        content = await self._get_reactable_content(content_id=content_id, viewer_id=viewer_id)
        if content.content_type != ContentTypeEnum.VIDEO:
            raise InvalidContentAction("View sessions are currently supported for videos only")
        return content

    async def _update_view_session(
        self,
        *,
        content_id: uuid.UUID,
        session_id: uuid.UUID,
        user: UserGet,
        data: ContentViewSessionHeartbeat,
    ) -> ContentViewSessionGet:
        content = await self._get_viewable_playback_content(content_id=content_id, viewer_id=user.user_id)
        session = await self._repository.get_view_session(
            view_session_id=session_id,
            content_id=content_id,
            viewer_id=user.user_id,
        )
        if session is None:
            raise ContentNotFound(f"View session with id {session_id!s} not found")

        duration_seconds = data.duration_seconds or self._content_duration_seconds(content)
        position = self._bounded_position(data.position_seconds, duration_seconds)
        max_position = max(session.max_position_seconds, position)
        watched_seconds = session.watched_seconds + (data.watched_seconds_delta or 0)
        progress_percent = self._progress_percent(max_position, duration_seconds)
        now = self._now()
        metadata = {**(session.view_metadata or {}), **data.metadata}
        source = data.source or session.source

        counted_date = session.counted_date
        counted_at = session.counted_at
        is_counted = session.is_counted
        increment_views = False
        if not is_counted:
            today = now.date()
            threshold = self._view_count_threshold(duration_seconds)
            qualifies = watched_seconds >= threshold or max_position >= threshold or data.ended
            already_counted = await self._repository.has_counted_view_on_date(
                content_id=content_id,
                viewer_id=user.user_id,
                counted_date=today,
            )
            if qualifies and not already_counted:
                is_counted = True
                counted_at = now
                counted_date = today
                increment_views = True

        views_count = await self._repository.update_view_session(
            view_session_id=session_id,
            last_seen_at=now,
            last_position_seconds=position,
            max_position_seconds=max_position,
            watched_seconds=watched_seconds,
            progress_percent=progress_percent,
            source=source,
            metadata=metadata,
            is_counted=is_counted,
            counted_at=counted_at,
            counted_date=counted_date,
            increment_views=increment_views,
            content_id=content_id,
        )
        updated = await self._repository.get_view_session(
            view_session_id=session_id,
            content_id=content_id,
            viewer_id=user.user_id,
        )
        assert updated is not None
        return self._build_view_session_get(updated, views_count=views_count)

    def _build_view_session_get(self, session, *, views_count: int = 0) -> ContentViewSessionGet:  # type: ignore[no-untyped-def]
        return ContentViewSessionGet(
            view_session_id=session.view_session_id,
            content_id=session.content_id,
            last_position_seconds=session.last_position_seconds,
            max_position_seconds=session.max_position_seconds,
            watched_seconds=session.watched_seconds,
            progress_percent=session.progress_percent,
            last_seen_at=session.last_seen_at,
            is_counted=session.is_counted,
            counted_at=session.counted_at,
            views_count=views_count,
        )

    def _build_history_progress_get(self, session) -> ContentHistoryProgressGet:  # type: ignore[no-untyped-def]
        return ContentHistoryProgressGet(
            last_position_seconds=session.last_position_seconds,
            max_position_seconds=session.max_position_seconds,
            watched_seconds=session.watched_seconds,
            progress_percent=session.progress_percent,
            last_seen_at=session.last_seen_at,
        )

    def _content_duration_seconds(self, content) -> int | None:  # type: ignore[no-untyped-def]
        if content.content_type == ContentTypeEnum.VIDEO and content.video_playback_details is not None:
            return content.video_playback_details.duration_seconds
        return None

    def _bounded_position(self, position_seconds: int, duration_seconds: int | None) -> int:
        position = max(0, int(position_seconds or 0))
        if duration_seconds is None or duration_seconds <= 0:
            return position
        return min(position, duration_seconds)

    def _progress_percent(self, position_seconds: int, duration_seconds: int | None) -> int:
        if duration_seconds is None or duration_seconds <= 0:
            return 0
        return max(0, min(100, int(round(position_seconds * 100 / duration_seconds))))

    def _view_count_threshold(self, duration_seconds: int | None) -> int:
        if duration_seconds is None or duration_seconds <= 0:
            return 30
        return math.ceil(min(30, max(5, duration_seconds * 0.3)))

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
