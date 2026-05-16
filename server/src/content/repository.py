from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy import and_, delete, desc, exists, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.models import AssetModel, ContentAssetModel
from src.assets.enums import AssetTypeEnum, AttachmentTypeEnum
import src.articles.models  # noqa: F401
import src.moments.models  # noqa: F401
import src.tags.models  # noqa: F401
import src.videos.models  # noqa: F401
from src.content.enums import (
    ContentProfileFilterEnum,
    ContentStatusEnum,
    ContentTypeEnum,
    ContentVisibilityEnum,
    ReactionTypeEnum,
)
from src.content.enums_list import ContentOrder
from src.content.models import ContentModel, ContentReactionModel, ContentViewSessionModel
from src.users.models import SubscriptionModel, UserModel
from src.videos.enums import VideoProcessingStatusEnum
from src.videos.models import VideoPlaybackDetailsModel


@dataclass(slots=True)
class ContentReactionSetResult:
    changed: bool
    previous_reaction: ReactionTypeEnum | None
    new_reaction: ReactionTypeEnum


@dataclass(slots=True)
class ContentReactionRemoveResult:
    removed: bool
    previous_reaction: ReactionTypeEnum | None


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        order: ContentOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_content_query(viewer_id=viewer_id)
            .outerjoin(VideoPlaybackDetailsModel)
            .where(ContentModel.content_type.in_([
                ContentTypeEnum.POST,
                ContentTypeEnum.ARTICLE,
                ContentTypeEnum.VIDEO,
                ContentTypeEnum.MOMENT,
            ]))
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .where(
                or_(
                    ContentModel.content_type.notin_([ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT]),
                    VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY,
                )
            )
            .order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def get_user_subscriptions_feed(
        self,
        *,
        user_id: uuid.UUID,
        content_type: ContentTypeEnum | None,
        order: ContentOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        subs_subquery = (
            select(SubscriptionModel.subscribed_id)
            .where(SubscriptionModel.subscriber_id == user_id)
            .subquery()
        )

        stmt = (
            self._build_content_query(viewer_id=user_id)
            .outerjoin(VideoPlaybackDetailsModel)
            .where(ContentModel.content_type.in_([
                ContentTypeEnum.POST,
                ContentTypeEnum.ARTICLE,
                ContentTypeEnum.VIDEO,
                ContentTypeEnum.MOMENT,
            ]))
            .where(ContentModel.author_id.in_(select(subs_subquery.c.subscribed_id)))
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .where(
                or_(
                    ContentModel.content_type.notin_([ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT]),
                    VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY,
                )
            )
        )
        if content_type is not None:
            stmt = stmt.where(ContentModel.content_type == content_type)
        stmt = (
            stmt
            .order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=user_id)

    async def get_single(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
    ) -> ContentModel | None:
        stmt = self._build_content_query(viewer_id=viewer_id).where(ContentModel.content_id == content_id)
        result = await self._session.execute(stmt)
        return self._one_or_none(result, viewer_id=viewer_id)

    async def get_video_recommendations(
        self,
        *,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        score = (
            ContentModel.views_count * 2
            + ContentModel.likes_count * 4
            + ContentModel.comments_count * 3
        )
        stmt = (
            self._video_ready_public_query(viewer_id=viewer_id)
            .order_by(desc(score), desc(ContentModel.published_at), desc(ContentModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def get_video_subscriptions(
        self,
        *,
        user_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        subs_subquery = (
            select(SubscriptionModel.subscribed_id)
            .where(SubscriptionModel.subscriber_id == user_id)
            .subquery()
        )
        stmt = (
            self._video_ready_public_query(viewer_id=user_id)
            .where(ContentModel.author_id.in_(select(subs_subquery.c.subscribed_id)))
            .order_by(desc(ContentModel.published_at), desc(ContentModel.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=user_id)

    async def get_history_sessions(
        self,
        *,
        viewer_id: uuid.UUID,
        content_type: ContentTypeEnum | None = None,
        offset: int,
        limit: int,
    ) -> list[tuple[ContentModel, ContentViewSessionModel]]:
        latest_subquery = (
            select(
                ContentViewSessionModel.content_id,
                func.max(ContentViewSessionModel.last_seen_at).label("last_seen_at"),
            )
            .where(ContentViewSessionModel.viewer_id == viewer_id)
            .group_by(ContentViewSessionModel.content_id)
            .subquery()
        )
        stmt = (
            select(ContentModel, ContentViewSessionModel)
            .join(latest_subquery, latest_subquery.c.content_id == ContentModel.content_id)
            .join(
                ContentViewSessionModel,
                and_(
                    ContentViewSessionModel.content_id == latest_subquery.c.content_id,
                    ContentViewSessionModel.last_seen_at == latest_subquery.c.last_seen_at,
                    ContentViewSessionModel.viewer_id == viewer_id,
                ),
            )
            .outerjoin(VideoPlaybackDetailsModel)
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            # TODO(activity): history currently exposes public content only; revisit if private owner history is needed.
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .where(
                or_(
                    ContentModel.content_type.notin_([ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT]),
                    VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY,
                )
            )
        )
        if content_type is not None:
            stmt = stmt.where(ContentModel.content_type == content_type)

        stmt = (
            stmt
            .options(
                selectinload(ContentModel.author).selectinload(UserModel.subscribers),
                selectinload(ContentModel.author)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
                selectinload(ContentModel.post_details),
                selectinload(ContentModel.article_details),
                selectinload(ContentModel.video_details),
                selectinload(ContentModel.moment_details),
                selectinload(ContentModel.video_playback_details),
                selectinload(ContentModel.tags),
                selectinload(ContentModel.asset_links)
                .selectinload(ContentAssetModel.asset)
                .selectinload(AssetModel.variants),
            )
            .order_by(desc(ContentViewSessionModel.last_seen_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = list(result.unique().all())
        items: list[tuple[ContentModel, ContentViewSessionModel]] = []
        for item, session in rows:
            item.my_reaction = await self._get_reaction_type(content_id=item.content_id, user_id=viewer_id)
            item.is_owner = item.author_id == viewer_id
            items.append((item, session))
        return items

    async def get_author_publications(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        content_type: ContentTypeEnum | None,
        profile_filter: ContentProfileFilterEnum,
        order: ContentOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_content_query(viewer_id=viewer_id)
            .outerjoin(VideoPlaybackDetailsModel)
            .where(
                ContentModel.content_type.in_(
                    [
                        ContentTypeEnum.POST,
                        ContentTypeEnum.ARTICLE,
                        ContentTypeEnum.VIDEO,
                        ContentTypeEnum.MOMENT,
                    ]
                )
            )
            .where(ContentModel.author_id == author_id)
            .where(ContentModel.deleted_at.is_(None))
            .where(
                or_(
                    ContentModel.content_type.notin_([ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT]),
                    VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY,
                )
            )
        )

        if content_type is not None:
            stmt = stmt.where(ContentModel.content_type == content_type)

        if viewer_id == author_id:
            if profile_filter == ContentProfileFilterEnum.ALL:
                stmt = stmt.where(
                    ContentModel.status.in_(
                        [
                            ContentStatusEnum.PUBLISHED,
                            ContentStatusEnum.DRAFT,
                        ]
                    )
                )
            elif profile_filter == ContentProfileFilterEnum.DRAFTS:
                stmt = stmt.where(ContentModel.status == ContentStatusEnum.DRAFT)
            elif profile_filter == ContentProfileFilterEnum.PRIVATE:
                stmt = (
                    stmt.where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                    .where(ContentModel.visibility == ContentVisibilityEnum.PRIVATE)
                )
            else:
                stmt = (
                    stmt.where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                    .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
                )
        else:
            stmt = (
                stmt.where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            )

        stmt = (
            stmt.order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def get_author_gallery_posts(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        profile_filter: ContentProfileFilterEnum,
        order: ContentOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        media_exists = exists(
            select(1)
            .select_from(ContentAssetModel)
            .join(AssetModel, ContentAssetModel.asset_id == AssetModel.asset_id)
            .where(ContentAssetModel.content_id == ContentModel.content_id)
            .where(ContentAssetModel.deleted_at.is_(None))
            .where(ContentAssetModel.attachment_type == AttachmentTypeEnum.MEDIA)
            .where(AssetModel.asset_type.in_([AssetTypeEnum.IMAGE, AssetTypeEnum.VIDEO]))
        )

        stmt = (
            self._build_content_query(viewer_id=viewer_id)
            .where(ContentModel.content_type == ContentTypeEnum.POST)
            .where(ContentModel.author_id == author_id)
            .where(ContentModel.deleted_at.is_(None))
            .where(media_exists)
        )

        if viewer_id == author_id:
            if profile_filter == ContentProfileFilterEnum.ALL:
                stmt = stmt.where(
                    ContentModel.status.in_(
                        [
                            ContentStatusEnum.PUBLISHED,
                            ContentStatusEnum.DRAFT,
                        ]
                    )
                )
            elif profile_filter == ContentProfileFilterEnum.DRAFTS:
                stmt = stmt.where(ContentModel.status == ContentStatusEnum.DRAFT)
            elif profile_filter == ContentProfileFilterEnum.PRIVATE:
                stmt = (
                    stmt.where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                    .where(ContentModel.visibility == ContentVisibilityEnum.PRIVATE)
                )
            else:
                stmt = (
                    stmt.where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                    .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
                )
        else:
            stmt = (
                stmt.where(ContentModel.status == ContentStatusEnum.PUBLISHED)
                .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            )

        stmt = (
            stmt.order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def set_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> ContentReactionSetResult:
        existing = await self._get_reaction(content_id=content_id, user_id=user_id)
        if existing is None:
            await self._session.execute(
                insert(ContentReactionModel).values(
                    content_id=content_id,
                    user_id=user_id,
                    reaction_type=reaction_type,
                )
            )
            await self._update_reaction_counters(
                content_id=content_id,
                like_delta=1 if reaction_type == ReactionTypeEnum.LIKE else 0,
                dislike_delta=1 if reaction_type == ReactionTypeEnum.DISLIKE else 0,
            )
            await self._session.commit()
            return ContentReactionSetResult(
                changed=True,
                previous_reaction=None,
                new_reaction=reaction_type,
            )
        if existing.reaction_type == reaction_type:
            return ContentReactionSetResult(
                changed=False,
                previous_reaction=existing.reaction_type,
                new_reaction=reaction_type,
            )
        previous_reaction = existing.reaction_type
        await self._session.execute(
            update(ContentReactionModel)
            .where(ContentReactionModel.content_id == content_id)
            .where(ContentReactionModel.user_id == user_id)
            .values(reaction_type=reaction_type)
        )
        await self._update_reaction_counters(
            content_id=content_id,
            like_delta=1 if reaction_type == ReactionTypeEnum.LIKE else -1,
            dislike_delta=1 if reaction_type == ReactionTypeEnum.DISLIKE else -1,
        )
        await self._session.commit()
        return ContentReactionSetResult(
            changed=True,
            previous_reaction=previous_reaction,
            new_reaction=reaction_type,
        )

    async def remove_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum | None = None,
    ) -> ContentReactionRemoveResult:
        existing = await self._get_reaction(content_id=content_id, user_id=user_id)
        if existing is None:
            return ContentReactionRemoveResult(removed=False, previous_reaction=None)
        if reaction_type is not None and existing.reaction_type != reaction_type:
            return ContentReactionRemoveResult(removed=False, previous_reaction=existing.reaction_type)
        previous_reaction = existing.reaction_type
        await self._session.execute(
            delete(ContentReactionModel)
            .where(ContentReactionModel.content_id == content_id)
            .where(ContentReactionModel.user_id == user_id)
        )
        await self._update_reaction_counters(
            content_id=content_id,
            like_delta=-1 if existing.reaction_type == ReactionTypeEnum.LIKE else 0,
            dislike_delta=-1 if existing.reaction_type == ReactionTypeEnum.DISLIKE else 0,
        )
        await self._session.commit()
        return ContentReactionRemoveResult(removed=True, previous_reaction=previous_reaction)

    async def create_view_session(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
        started_at: datetime.datetime,
        last_position_seconds: int,
        max_position_seconds: int,
        watched_seconds: int,
        progress_percent: int,
        last_seen_at: datetime.datetime | None = None,
        is_counted: bool = False,
        counted_at: datetime.datetime | None = None,
        counted_date: datetime.date | None = None,
        increment_views: bool = False,
        source: str | None,
        metadata: dict,
    ) -> ContentViewSessionModel:
        result = await self._session.execute(
            insert(ContentViewSessionModel)
            .values(
                content_id=content_id,
                viewer_id=viewer_id,
                started_at=started_at,
                last_seen_at=last_seen_at or started_at,
                last_position_seconds=last_position_seconds,
                max_position_seconds=max_position_seconds,
                watched_seconds=watched_seconds,
                progress_percent=progress_percent,
                is_counted=is_counted,
                counted_at=counted_at,
                counted_date=counted_date,
                source=source,
                view_metadata=metadata,
            )
            .returning(ContentViewSessionModel.view_session_id)
        )
        if increment_views:
            await self._session.execute(
                update(ContentModel)
                .where(ContentModel.content_id == content_id)
                .values(views_count=ContentModel.views_count + 1)
            )
        await self._session.commit()
        session = await self.get_view_session(
            view_session_id=result.scalar_one(),
            content_id=content_id,
            viewer_id=viewer_id,
        )
        assert session is not None
        return session

    async def get_view_session(
        self,
        *,
        view_session_id: uuid.UUID,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> ContentViewSessionModel | None:
        result = await self._session.execute(
            select(ContentViewSessionModel)
            .where(ContentViewSessionModel.view_session_id == view_session_id)
            .where(ContentViewSessionModel.content_id == content_id)
            .where(ContentViewSessionModel.viewer_id == viewer_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_view_session(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> ContentViewSessionModel | None:
        result = await self._session.execute(
            select(ContentViewSessionModel)
            .where(ContentViewSessionModel.content_id == content_id)
            .where(ContentViewSessionModel.viewer_id == viewer_id)
            .order_by(desc(ContentViewSessionModel.last_seen_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_view_session(
        self,
        *,
        view_session_id: uuid.UUID,
        last_seen_at: datetime.datetime,
        last_position_seconds: int,
        max_position_seconds: int,
        watched_seconds: int,
        progress_percent: int,
        source: str | None,
        metadata: dict,
        is_counted: bool,
        counted_at: datetime.datetime | None,
        counted_date: datetime.date | None,
        increment_views: bool,
        content_id: uuid.UUID,
    ) -> int:
        values = {
            "last_seen_at": last_seen_at,
            "last_position_seconds": last_position_seconds,
            "max_position_seconds": max_position_seconds,
            "watched_seconds": watched_seconds,
            "progress_percent": progress_percent,
            "source": source,
            "view_metadata": metadata,
            "is_counted": is_counted,
            "counted_at": counted_at,
            "counted_date": counted_date,
        }
        await self._session.execute(
            update(ContentViewSessionModel)
            .where(ContentViewSessionModel.view_session_id == view_session_id)
            .values(**values)
        )
        if increment_views:
            await self._session.execute(
                update(ContentModel)
                .where(ContentModel.content_id == content_id)
                .values(views_count=ContentModel.views_count + 1)
            )
        await self._session.commit()
        views_count = await self._session.scalar(
            select(ContentModel.views_count).where(ContentModel.content_id == content_id)
        )
        return int(views_count or 0)

    async def has_counted_view_on_date(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
        counted_date: datetime.date,
    ) -> bool:
        result = await self._session.scalar(
            select(
                exists().where(
                    ContentViewSessionModel.content_id == content_id,
                    ContentViewSessionModel.viewer_id == viewer_id,
                    ContentViewSessionModel.counted_date == counted_date,
                    ContentViewSessionModel.is_counted.is_(True),
                )
            )
        )
        return bool(result)

    async def get_views_count(self, *, content_id: uuid.UUID) -> int:
        views_count = await self._session.scalar(
            select(ContentModel.views_count).where(ContentModel.content_id == content_id)
        )
        return int(views_count or 0)

    def _build_content_query(self, viewer_id: uuid.UUID | None):
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)
        base_options = (
            selectinload(ContentModel.author).selectinload(UserModel.subscribers),
            selectinload(ContentModel.author)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants),
            selectinload(ContentModel.post_details),
            selectinload(ContentModel.article_details),
            selectinload(ContentModel.video_details),
            selectinload(ContentModel.moment_details),
            selectinload(ContentModel.video_playback_details),
            selectinload(ContentModel.tags),
            selectinload(ContentModel.asset_links)
            .selectinload(ContentAssetModel.asset)
            .selectinload(AssetModel.variants),
        )

        if reaction_subquery is None:
            return select(ContentModel).options(*base_options)

        return (
            select(
                ContentModel,
                reaction_subquery.c.reaction_type.label("my_reaction"),
            )
            .outerjoin(
                reaction_subquery,
                ContentModel.content_id == reaction_subquery.c.content_id,
            )
            .options(*base_options)
        )

    def _video_ready_public_query(self, viewer_id: uuid.UUID | None):
        return (
            self._build_content_query(viewer_id=viewer_id)
            .join(VideoPlaybackDetailsModel)
            .where(ContentModel.content_type == ContentTypeEnum.VIDEO)
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .where(VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY)
        )

    def _reaction_subquery(self, viewer_id: uuid.UUID | None):
        if viewer_id is None:
            return None

        return (
            select(
                ContentReactionModel.content_id,
                ContentReactionModel.reaction_type,
            )
            .where(ContentReactionModel.user_id == viewer_id)
            .subquery()
        )

    def _many(self, result, viewer_id: uuid.UUID | None) -> list[ContentModel]:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            items = list(result.scalars().unique().all())
            for item in items:
                item.my_reaction = None
                item.is_owner = False
            return items

        items: list[ContentModel] = []
        for item, my_reaction in result.unique().all():
            item.my_reaction = my_reaction
            item.is_owner = item.author_id == viewer_id
            items.append(item)
        return items

    def _one_or_none(self, result, viewer_id: uuid.UUID | None) -> ContentModel | None:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            item = result.scalar_one_or_none()
            if item is not None:
                item.my_reaction = None
                item.is_owner = False
            return item
        row = result.one_or_none()
        if row is None:
            return None
        item, my_reaction = row
        item.my_reaction = my_reaction
        item.is_owner = item.author_id == viewer_id
        return item

    async def _get_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ContentReactionModel | None:
        result = await self._session.execute(
            select(ContentReactionModel)
            .where(ContentReactionModel.content_id == content_id)
            .where(ContentReactionModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _get_reaction_type(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ReactionTypeEnum | None:
        reaction = await self._get_reaction(content_id=content_id, user_id=user_id)
        return reaction.reaction_type if reaction is not None else None

    async def _update_reaction_counters(
        self,
        *,
        content_id: uuid.UUID,
        like_delta: int,
        dislike_delta: int,
    ) -> None:
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(
                likes_count=ContentModel.likes_count + like_delta,
                dislikes_count=ContentModel.dislikes_count + dislike_delta,
            )
        )

    def _order_by_clause(self, order: ContentOrder, order_desc: bool):
        order_mapping = {
            ContentOrder.ID: ContentModel.content_id,
            ContentOrder.CREATED_AT: ContentModel.created_at,
            ContentOrder.UPDATED_AT: ContentModel.updated_at,
            ContentOrder.PUBLISHED_AT: ContentModel.published_at,
        }
        column = order_mapping[order]
        return desc(column) if order_desc else column
