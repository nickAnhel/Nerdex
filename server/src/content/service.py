from __future__ import annotations

import datetime
import math
import uuid
from typing import TYPE_CHECKING

from src.content.access import can_view_content
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ReactionTypeEnum
from src.content.enums_list import ContentOrder
from src.content.exceptions import ContentNotFound
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

if TYPE_CHECKING:
    from src.activity.service import ActivityService
    from src.assets.storage import AssetStorage
    from src.content.projectors import ContentProjectorRegistry


class ContentService:
    def __init__(
        self,
        repository: ContentRepository,
        asset_storage: AssetStorage,
        projector_registry: ContentProjectorRegistry,
        activity_service: ActivityService | None = None,
    ) -> None:
        self._repository = repository
        self._asset_storage = asset_storage
        self._projector_registry = projector_registry
        self._activity_service = activity_service

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
        content = await self._get_reactable_content(content_id=content_id, viewer_id=user.user_id)
        result = await self._repository.set_reaction(
            content_id=content_id,
            user_id=user.user_id,
            reaction_type=reaction_type,
        )
        if self._activity_service is not None and getattr(result, "changed", False):
            await self._activity_service.log_content_reaction(
                user_id=user.user_id,
                content_id=content_id,
                content_type=content.content_type,
                previous_reaction=result.previous_reaction,
                new_reaction=result.new_reaction,
            )
        return await self._build_reaction_get(content_id=content_id, viewer_id=user.user_id)

    async def remove_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user: UserGet,
        reaction_type: ReactionTypeEnum | None = None,
    ) -> ContentReactionGet:
        content = await self._get_reactable_content(content_id=content_id, viewer_id=user.user_id)
        result = await self._repository.remove_reaction(
            content_id=content_id,
            user_id=user.user_id,
            reaction_type=reaction_type,
        )
        if (
            self._activity_service is not None
            and getattr(result, "removed", False)
            and result.previous_reaction is not None
        ):
            await self._activity_service.log_content_reaction_removed(
                user_id=user.user_id,
                content_id=content_id,
                content_type=content.content_type,
                previous_reaction=result.previous_reaction,
            )
        return await self._build_reaction_get(content_id=content_id, viewer_id=user.user_id)

    async def start_view_session(
        self,
        *,
        content_id: uuid.UUID,
        user: UserGet,
        data: ContentViewSessionStart,
    ) -> ContentViewSessionGet:
        content = await self._get_trackable_content(content_id=content_id, viewer_id=user.user_id)
        duration_seconds = self._content_duration_seconds(content)
        now = self._now()
        latest = await self._repository.get_latest_view_session(
            content_id=content_id,
            viewer_id=user.user_id,
        )
        initial_state = self._initial_view_session_state(
            content=content,
            data=data,
            latest=latest,
            duration_seconds=duration_seconds,
        )
        counted_at = None
        counted_date = None
        is_counted = False
        increment_views = False
        if content.content_type == ContentTypeEnum.POST:
            already_counted = await self._repository.has_counted_view_on_date(
                content_id=content_id,
                viewer_id=user.user_id,
                counted_date=now.date(),
            )
            if not already_counted:
                is_counted = True
                counted_at = now
                counted_date = now.date()
                increment_views = self._should_increment_public_views(content=content, user_id=user.user_id)

        session = await self._repository.create_view_session(
            content_id=content_id,
            viewer_id=user.user_id,
            started_at=now,
            last_position_seconds=initial_state["last_position_seconds"],
            max_position_seconds=initial_state["max_position_seconds"],
            watched_seconds=initial_state["watched_seconds"],
            progress_percent=initial_state["progress_percent"],
            is_counted=is_counted,
            counted_at=counted_at,
            counted_date=counted_date,
            increment_views=increment_views,
            source=data.source,
            metadata=data.metadata,
        )
        views_count = await self._repository.get_views_count(content_id=content_id)
        if self._activity_service is not None and is_counted:
            await self._activity_service.log_content_view(
                user_id=user.user_id,
                content_id=content_id,
                content_type=content.content_type,
                view_session_id=session.view_session_id,
                source=session.source,
                progress_percent=session.progress_percent,
                watched_seconds=session.watched_seconds,
                position_seconds=session.last_position_seconds,
            )
        return self._build_view_session_get(session, views_count=views_count)

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

    async def get_shareable_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> ContentListItemGet:
        content = await self._get_reactable_content(content_id=content_id, viewer_id=viewer_id)
        return await self._build_message_share_preview_item(content, viewer_id=viewer_id)

    async def _build_message_share_preview_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID,
    ) -> ContentListItemGet:
        payload = {
            "content_id": item.content_id,
            "content_type": item.content_type,
            "status": item.status,
            "visibility": item.visibility,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "published_at": item.published_at,
            "comments_count": item.comments_count,
            "likes_count": item.likes_count,
            "dislikes_count": item.dislikes_count,
            "views_count": getattr(item, "views_count", 0),
            "user": await self._build_share_preview_author(item, viewer_id=viewer_id),
            "tags": item.tags,
            "my_reaction": item.my_reaction,
            "is_owner": item.author_id == viewer_id,
        }

        if item.content_type == ContentTypeEnum.POST:
            return ContentListItemGet(
                **payload,
                post_content=item.post_details.body_text if item.post_details is not None else "",
            )

        if item.content_type == ContentTypeEnum.ARTICLE:
            return ContentListItemGet(
                **payload,
                title=item.title,
                excerpt=item.excerpt,
                slug=item.article_details.slug if item.article_details is not None else None,
                canonical_path=f"/articles/{item.content_id}",
                reading_time_minutes=(
                    item.article_details.reading_time_minutes
                    if item.article_details is not None
                    else None
                ),
                word_count=(
                    item.article_details.word_count
                    if item.article_details is not None
                    else None
                ),
            )

        if item.content_type == ContentTypeEnum.VIDEO:
            playback = item.video_playback_details
            details = item.video_details
            return ContentListItemGet(
                **payload,
                title=item.title,
                description=details.description if details is not None else None,
                excerpt=item.excerpt,
                canonical_path=f"/videos/{item.content_id}",
                duration_seconds=playback.duration_seconds if playback is not None else None,
                orientation=playback.orientation if playback is not None else None,
                processing_status=playback.processing_status if playback is not None else None,
                processing_error=playback.processing_error if playback is not None else None,
            )

        if item.content_type == ContentTypeEnum.MOMENT:
            playback = item.video_playback_details
            details = item.moment_details
            caption = details.caption if details is not None else None
            return ContentListItemGet(
                **payload,
                caption=caption,
                excerpt=caption,
                canonical_path=f"/moments?moment={item.content_id}",
                duration_seconds=playback.duration_seconds if playback is not None else None,
                orientation=playback.orientation if playback is not None else None,
                processing_status=playback.processing_status if playback is not None else None,
                processing_error=playback.processing_error if playback is not None else None,
            )

        return ContentListItemGet(**payload)

    async def _build_share_preview_author(
        self,
        item,
        *,
        viewer_id: uuid.UUID,
    ) -> UserGet:
        from src.users.presentation import build_user_get

        return await build_user_get(
            item.author,
            viewer_id=viewer_id,
            storage=None,
        )

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
            content.content_type in {ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT}
            and (
                content.video_playback_details is None
                or content.video_playback_details.processing_status != VideoProcessingStatusEnum.READY
            )
        ):
            raise ContentNotFound(f"Content with id {content_id!s} not found")
        return content

    async def _get_trackable_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        content = await self._get_reactable_content(content_id=content_id, viewer_id=viewer_id)
        if content.content_type not in {
            ContentTypeEnum.POST,
            ContentTypeEnum.ARTICLE,
            ContentTypeEnum.VIDEO,
            ContentTypeEnum.MOMENT,
        }:
            raise ContentNotFound(f"Content with id {content_id!s} not found")
        return content

    async def _update_view_session(
        self,
        *,
        content_id: uuid.UUID,
        session_id: uuid.UUID,
        user: UserGet,
        data: ContentViewSessionHeartbeat,
    ) -> ContentViewSessionGet:
        content = await self._get_trackable_content(content_id=content_id, viewer_id=user.user_id)
        session = await self._repository.get_view_session(
            view_session_id=session_id,
            content_id=content_id,
            viewer_id=user.user_id,
        )
        if session is None:
            raise ContentNotFound(f"View session with id {session_id!s} not found")

        duration_seconds = data.duration_seconds or self._content_duration_seconds(content)
        position = self._session_position(
            content=content,
            session=session,
            position_seconds=data.position_seconds,
            duration_seconds=duration_seconds,
        )
        max_position = self._session_max_position(content=content, session=session, position=position)
        watched_seconds = session.watched_seconds + (data.watched_seconds_delta or 0)
        progress_percent = self._session_progress_percent(
            content=content,
            session=session,
            data=data,
            max_position=max_position,
            duration_seconds=duration_seconds,
        )
        now = self._now()
        metadata = {**(session.view_metadata or {}), **data.metadata}
        source = data.source or session.source

        counted_date = session.counted_date
        counted_at = session.counted_at
        is_counted = session.is_counted
        was_counted = session.is_counted
        increment_views = False
        if not is_counted:
            today = now.date()
            qualifies = self._view_qualifies(
                content=content,
                duration_seconds=duration_seconds,
                watched_seconds=watched_seconds,
                max_position=max_position,
                progress_percent=progress_percent,
                ended=data.ended,
            )
            already_counted = await self._repository.has_counted_view_on_date(
                content_id=content_id,
                viewer_id=user.user_id,
                counted_date=today,
            )
            if qualifies and not already_counted:
                is_counted = True
                counted_at = now
                counted_date = today
                increment_views = self._should_increment_public_views(content=content, user_id=user.user_id)

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
        if self._activity_service is not None and not was_counted and updated.is_counted:
            await self._activity_service.log_content_view(
                user_id=user.user_id,
                content_id=content_id,
                content_type=content.content_type,
                view_session_id=updated.view_session_id,
                source=updated.source,
                progress_percent=updated.progress_percent,
                watched_seconds=updated.watched_seconds,
                position_seconds=updated.last_position_seconds,
            )
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
        if content.content_type in {ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT} and content.video_playback_details is not None:
            return content.video_playback_details.duration_seconds
        return None

    def _initial_view_session_state(
        self,
        *,
        content,
        data: ContentViewSessionStart,
        latest,
        duration_seconds: int | None,
    ) -> dict[str, int]:  # type: ignore[no-untyped-def]
        if content.content_type == ContentTypeEnum.POST:
            return {
                "last_position_seconds": 0,
                "max_position_seconds": 0,
                "watched_seconds": 0,
                "progress_percent": 100,
            }

        if content.content_type == ContentTypeEnum.ARTICLE:
            requested_progress = data.initial_progress_percent or 0
            return {
                "last_position_seconds": 0,
                "max_position_seconds": 0,
                "watched_seconds": latest.watched_seconds if latest is not None else 0,
                "progress_percent": max(
                    latest.progress_percent if latest is not None else 0,
                    requested_progress,
                ),
            }

        position = self._bounded_position(data.initial_position_seconds, duration_seconds)
        state = {
            "last_position_seconds": position,
            "max_position_seconds": position,
            "watched_seconds": 0,
            "progress_percent": self._progress_percent(position, duration_seconds),
        }
        if latest is not None:
            state["last_position_seconds"] = latest.last_position_seconds
            state["max_position_seconds"] = latest.max_position_seconds
            state["watched_seconds"] = latest.watched_seconds
            state["progress_percent"] = latest.progress_percent
        return state

    def _session_position(
        self,
        *,
        content,
        session,
        position_seconds: int | None,
        duration_seconds: int | None,
    ) -> int:  # type: ignore[no-untyped-def]
        if content.content_type in {ContentTypeEnum.POST, ContentTypeEnum.ARTICLE}:
            return session.last_position_seconds
        if position_seconds is None:
            return session.last_position_seconds
        return self._bounded_position(position_seconds, duration_seconds)

    def _session_max_position(self, *, content, session, position: int) -> int:  # type: ignore[no-untyped-def]
        if content.content_type in {ContentTypeEnum.POST, ContentTypeEnum.ARTICLE}:
            return session.max_position_seconds
        return max(session.max_position_seconds, position)

    def _session_progress_percent(
        self,
        *,
        content,
        session,
        data: ContentViewSessionHeartbeat,
        max_position: int,
        duration_seconds: int | None,
    ) -> int:  # type: ignore[no-untyped-def]
        if content.content_type == ContentTypeEnum.POST:
            return 100
        if content.content_type == ContentTypeEnum.ARTICLE:
            return max(session.progress_percent, data.progress_percent or 0)
        return self._progress_percent(max_position, duration_seconds)

    def _bounded_position(self, position_seconds: int | None, duration_seconds: int | None) -> int:
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

    def _view_qualifies(
        self,
        *,
        content,
        duration_seconds: int | None,
        watched_seconds: int,
        max_position: int,
        progress_percent: int,
        ended: bool,
    ) -> bool:  # type: ignore[no-untyped-def]
        if content.content_type == ContentTypeEnum.POST:
            return True
        if content.content_type == ContentTypeEnum.ARTICLE:
            return progress_percent >= 25 or watched_seconds >= 10
        if content.content_type == ContentTypeEnum.MOMENT:
            return watched_seconds >= 2 or progress_percent >= 50
        threshold = self._view_count_threshold(duration_seconds)
        return watched_seconds >= threshold or max_position >= threshold or ended

    def _should_increment_public_views(self, *, content, user_id: uuid.UUID) -> bool:  # type: ignore[no-untyped-def]
        return not (
            content.content_type == ContentTypeEnum.MOMENT
            and content.author_id == user_id
        )

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
