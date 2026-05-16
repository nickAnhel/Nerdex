from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.activity.models import ActivityEventModel
from src.assets.models import AssetModel, ContentAssetModel
import src.articles.models  # noqa: F401
import src.moments.models  # noqa: F401
from src.comments.models import CommentModel
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.models import ContentModel, ContentReactionModel, ContentViewSessionModel
import src.tags.models  # noqa: F401
from src.tags.models import ContentTagModel, TagModel
from src.users.models import SubscriptionModel, UserModel
from src.videos.enums import VideoProcessingStatusEnum
from src.videos.models import VideoPlaybackDetailsModel


@dataclass(slots=True)
class ContentGraphRow:
    content_id: uuid.UUID
    author_id: uuid.UUID
    content_type: ContentTypeEnum
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    published_at: datetime.datetime | None
    likes_count: int
    dislikes_count: int
    comments_count: int
    views_count: int


@dataclass(slots=True)
class ContentTagGraphRow:
    content_id: uuid.UUID
    tag_id: uuid.UUID
    tag_slug: str


@dataclass(slots=True)
class ContentReactionGraphRow:
    user_id: uuid.UUID
    content_id: uuid.UUID
    reaction_type: ReactionTypeEnum
    created_at: datetime.datetime


@dataclass(slots=True)
class ContentViewedGraphRow:
    user_id: uuid.UUID
    content_id: uuid.UUID
    views_count: int
    progress_percent: int
    last_seen_at: datetime.datetime


@dataclass(slots=True)
class ContentCommentedGraphRow:
    user_id: uuid.UUID
    content_id: uuid.UUID
    comments_count: int
    last_commented_at: datetime.datetime


@dataclass(slots=True)
class ActivityEventGraphRow:
    activity_event_id: uuid.UUID
    created_at: datetime.datetime
    action_type: str
    user_id: uuid.UUID
    content_id: uuid.UUID | None
    target_user_id: uuid.UUID | None
    metadata: dict


@dataclass(slots=True)
class ActivityCursor:
    created_at: datetime.datetime
    activity_event_id: uuid.UUID


class RecommendationPostgresRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all_user_ids(self) -> list[uuid.UUID]:
        result = await self._session.execute(select(UserModel.user_id))
        return list(result.scalars().all())

    async def get_user_ids_by_ids(self, user_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        if not user_ids:
            return []
        result = await self._session.execute(
            select(UserModel.user_id).where(UserModel.user_id.in_(user_ids))
        )
        return list(result.scalars().all())

    async def get_users_by_ids(self, *, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, UserModel]:
        if not user_ids:
            return {}

        result = await self._session.execute(
            select(UserModel)
            .where(UserModel.user_id.in_(user_ids))
            .options(selectinload(UserModel.subscribers))
            .options(
                selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants)
            )
        )
        users = list(result.scalars().all())
        return {user.user_id: user for user in users}

    async def get_subscribed_user_ids(self, *, subscriber_id: uuid.UUID) -> set[uuid.UUID]:
        result = await self._session.execute(
            select(SubscriptionModel.subscribed_id)
            .where(SubscriptionModel.subscriber_id == subscriber_id)
        )
        return set(result.scalars().all())

    async def get_public_author_ids_by_ids(self, *, author_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not author_ids:
            return set()

        result = await self._session.execute(
            select(ContentModel.author_id)
            .outerjoin(VideoPlaybackDetailsModel, VideoPlaybackDetailsModel.content_id == ContentModel.content_id)
            .where(ContentModel.author_id.in_(author_ids))
            .where(*self._content_visibility_clauses())
            .group_by(ContentModel.author_id)
        )
        return set(result.scalars().all())

    async def get_all_subscriptions(self) -> list[tuple[uuid.UUID, uuid.UUID]]:
        result = await self._session.execute(
            select(SubscriptionModel.subscriber_id, SubscriptionModel.subscribed_id)
        )
        return [(row.subscriber_id, row.subscribed_id) for row in result.all()]

    async def get_all_content_nodes(self) -> list[ContentGraphRow]:
        return await self._get_content_nodes_query()

    async def get_content_nodes_by_ids(self, content_ids: list[uuid.UUID]) -> list[ContentGraphRow]:
        if not content_ids:
            return []
        return await self._get_content_nodes_query(content_ids=content_ids)

    async def get_all_content_tags(self) -> list[ContentTagGraphRow]:
        return await self._get_content_tags_query()

    async def get_content_tags_by_content_ids(self, content_ids: list[uuid.UUID]) -> list[ContentTagGraphRow]:
        if not content_ids:
            return []
        return await self._get_content_tags_query(content_ids=content_ids)

    async def get_all_content_reactions(self) -> list[ContentReactionGraphRow]:
        result = await self._session.execute(
            select(
                ContentReactionModel.user_id,
                ContentReactionModel.content_id,
                ContentReactionModel.reaction_type,
                ContentReactionModel.created_at,
            )
            .where(ContentReactionModel.reaction_type.in_([ReactionTypeEnum.LIKE, ReactionTypeEnum.DISLIKE]))
        )
        return [
            ContentReactionGraphRow(
                user_id=row.user_id,
                content_id=row.content_id,
                reaction_type=row.reaction_type,
                created_at=row.created_at,
            )
            for row in result.all()
        ]

    async def get_all_content_views(self) -> list[ContentViewedGraphRow]:
        result = await self._session.execute(
            select(
                ContentViewSessionModel.viewer_id,
                ContentViewSessionModel.content_id,
                func.count(ContentViewSessionModel.view_session_id).label("views_count"),
                func.max(ContentViewSessionModel.progress_percent).label("progress_percent"),
                func.max(ContentViewSessionModel.last_seen_at).label("last_seen_at"),
            )
            .where(ContentViewSessionModel.viewer_id.is_not(None))
            .group_by(ContentViewSessionModel.viewer_id, ContentViewSessionModel.content_id)
        )
        return [
            ContentViewedGraphRow(
                user_id=row.viewer_id,
                content_id=row.content_id,
                views_count=int(row.views_count or 0),
                progress_percent=int(row.progress_percent or 0),
                last_seen_at=row.last_seen_at,
            )
            for row in result.all()
            if row.viewer_id is not None and row.last_seen_at is not None
        ]

    async def get_all_content_comments(self) -> list[ContentCommentedGraphRow]:
        result = await self._session.execute(
            select(
                CommentModel.author_id,
                CommentModel.content_id,
                func.count(CommentModel.comment_id).label("comments_count"),
                func.max(CommentModel.created_at).label("last_commented_at"),
            )
            .where(CommentModel.deleted_at.is_(None))
            .group_by(CommentModel.author_id, CommentModel.content_id)
        )
        return [
            ContentCommentedGraphRow(
                user_id=row.author_id,
                content_id=row.content_id,
                comments_count=int(row.comments_count or 0),
                last_commented_at=row.last_commented_at,
            )
            for row in result.all()
            if row.last_commented_at is not None
        ]

    async def get_latest_activity_cursor(self) -> ActivityCursor | None:
        result = await self._session.execute(
            select(ActivityEventModel.created_at, ActivityEventModel.activity_event_id)
            .order_by(desc(ActivityEventModel.created_at), desc(ActivityEventModel.activity_event_id))
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return ActivityCursor(created_at=row.created_at, activity_event_id=row.activity_event_id)

    async def get_activity_events_since(
        self,
        *,
        created_at: datetime.datetime | None,
        activity_event_id: uuid.UUID | None,
        limit: int,
    ) -> list[ActivityEventGraphRow]:
        stmt = select(
            ActivityEventModel.activity_event_id,
            ActivityEventModel.created_at,
            ActivityEventModel.action_type,
            ActivityEventModel.user_id,
            ActivityEventModel.content_id,
            ActivityEventModel.target_user_id,
            ActivityEventModel.event_metadata,
        )

        if created_at is not None:
            if activity_event_id is None:
                stmt = stmt.where(ActivityEventModel.created_at > created_at)
            else:
                stmt = stmt.where(
                    or_(
                        ActivityEventModel.created_at > created_at,
                        and_(
                            ActivityEventModel.created_at == created_at,
                            ActivityEventModel.activity_event_id > activity_event_id,
                        ),
                    )
                )

        result = await self._session.execute(
            stmt
            .order_by(ActivityEventModel.created_at.asc(), ActivityEventModel.activity_event_id.asc())
            .limit(limit)
        )

        return [
            ActivityEventGraphRow(
                activity_event_id=row.activity_event_id,
                created_at=row.created_at,
                action_type=row.action_type.value,
                user_id=row.user_id,
                content_id=row.content_id,
                target_user_id=row.target_user_id,
                metadata=dict(row.event_metadata or {}),
            )
            for row in result.all()
        ]

    async def get_visible_content_by_ids(
        self,
        *,
        content_ids: list[uuid.UUID],
        viewer_id: uuid.UUID | None,
    ) -> dict[uuid.UUID, ContentModel]:
        if not content_ids:
            return {}

        query = (
            self._build_content_query(viewer_id=viewer_id)
            .outerjoin(VideoPlaybackDetailsModel)
            .where(ContentModel.content_id.in_(content_ids))
            .where(*self._content_visibility_clauses())
        )
        result = await self._session.execute(query)

        if viewer_id is None:
            items = list(result.scalars().unique().all())
            for item in items:
                item.my_reaction = None
                item.is_owner = False
            return {item.content_id: item for item in items}

        items: dict[uuid.UUID, ContentModel] = {}
        for item, my_reaction in result.unique().all():
            item.my_reaction = my_reaction
            item.is_owner = item.author_id == viewer_id
            items[item.content_id] = item
        return items

    async def get_recommendation_fallback_content(
        self,
        *,
        viewer_id: uuid.UUID | None,
        content_type: ContentTypeEnum | None,
        sort: str,
        offset: int,
        limit: int,
        exclude_content_ids: list[uuid.UUID],
    ) -> list[ContentModel]:
        query = (
            self._build_content_query(viewer_id=viewer_id)
            .outerjoin(VideoPlaybackDetailsModel)
            .where(*self._content_visibility_clauses())
        )

        if content_type is not None:
            query = query.where(ContentModel.content_type == content_type)
        if exclude_content_ids:
            query = query.where(ContentModel.content_id.notin_(exclude_content_ids))

        if viewer_id is not None:
            disliked_subquery = (
                select(ContentReactionModel.content_id)
                .where(ContentReactionModel.user_id == viewer_id)
                .where(ContentReactionModel.reaction_type == ReactionTypeEnum.DISLIKE)
                .subquery()
            )
            finished_subquery = (
                select(ContentViewSessionModel.content_id)
                .where(ContentViewSessionModel.viewer_id == viewer_id)
                .where(ContentViewSessionModel.progress_percent >= 90)
                .group_by(ContentViewSessionModel.content_id)
                .subquery()
            )
            query = (
                query
                .where(ContentModel.author_id != viewer_id)
                .where(ContentModel.content_id.notin_(select(disliked_subquery.c.content_id)))
                .where(ContentModel.content_id.notin_(select(finished_subquery.c.content_id)))
            )

        published_sort = func.coalesce(ContentModel.published_at, ContentModel.created_at)
        if sort == "oldest":
            query = query.order_by(published_sort.asc())
        elif sort == "newest":
            query = query.order_by(desc(published_sort))
        else:
            relevance_score = (
                (ContentModel.likes_count * 4)
                - (ContentModel.dislikes_count * 6)
                + (ContentModel.comments_count * 5)
                + ContentModel.views_count
            )
            query = query.order_by(desc(relevance_score), desc(published_sort))

        result = await self._session.execute(query.offset(offset).limit(limit))

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

    async def _get_content_nodes_query(
        self,
        *,
        content_ids: list[uuid.UUID] | None = None,
    ) -> list[ContentGraphRow]:
        stmt = select(
            ContentModel.content_id,
            ContentModel.author_id,
            ContentModel.content_type,
            ContentModel.status,
            ContentModel.visibility,
            ContentModel.created_at,
            ContentModel.published_at,
            ContentModel.likes_count,
            ContentModel.dislikes_count,
            ContentModel.comments_count,
            ContentModel.views_count,
        )

        if content_ids is not None:
            stmt = stmt.where(ContentModel.content_id.in_(content_ids))

        result = await self._session.execute(stmt)
        return [
            ContentGraphRow(
                content_id=row.content_id,
                author_id=row.author_id,
                content_type=row.content_type,
                status=row.status,
                visibility=row.visibility,
                created_at=row.created_at,
                published_at=row.published_at,
                likes_count=row.likes_count,
                dislikes_count=row.dislikes_count,
                comments_count=row.comments_count,
                views_count=row.views_count,
            )
            for row in result.all()
        ]

    async def _get_content_tags_query(
        self,
        *,
        content_ids: list[uuid.UUID] | None = None,
    ) -> list[ContentTagGraphRow]:
        stmt = (
            select(
                ContentTagModel.content_id,
                ContentTagModel.tag_id,
                TagModel.slug,
            )
            .join(TagModel, TagModel.tag_id == ContentTagModel.tag_id)
        )
        if content_ids is not None:
            stmt = stmt.where(ContentTagModel.content_id.in_(content_ids))

        result = await self._session.execute(stmt)
        return [
            ContentTagGraphRow(
                content_id=row.content_id,
                tag_id=row.tag_id,
                tag_slug=row.slug,
            )
            for row in result.all()
        ]

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

    def _content_visibility_clauses(self) -> list:
        return [
            ContentModel.content_type.in_(
                [
                    ContentTypeEnum.POST,
                    ContentTypeEnum.ARTICLE,
                    ContentTypeEnum.VIDEO,
                    ContentTypeEnum.MOMENT,
                ]
            ),
            ContentModel.status == ContentStatusEnum.PUBLISHED,
            ContentModel.visibility == ContentVisibilityEnum.PUBLIC,
            ContentModel.deleted_at.is_(None),
            or_(
                ContentModel.content_type.notin_([ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT]),
                and_(
                    VideoPlaybackDetailsModel.content_id.is_not(None),
                    VideoPlaybackDetailsModel.processing_status == VideoProcessingStatusEnum.READY,
                ),
            ),
        ]
