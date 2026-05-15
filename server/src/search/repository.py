from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, desc, func, literal, literal_column, or_, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.models import AssetModel, ContentAssetModel
import src.articles.models  # noqa: F401
import src.chats.models  # noqa: F401
import src.comments.models  # noqa: F401
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.content.models import ContentModel, ContentReactionModel
import src.events.models  # noqa: F401
import src.moments.models  # noqa: F401
import src.messages.models  # noqa: F401
import src.posts.models  # noqa: F401
from src.search.enums import SearchSortEnum
import src.tags.models  # noqa: F401
from src.users.models import UserModel
from src.videos.enums import VideoProcessingStatusEnum
from src.videos.models import VideoPlaybackDetailsModel


@dataclass(slots=True)
class SearchContentMatch:
    content_id: uuid.UUID
    score: float


@dataclass(slots=True)
class SearchAuthorMatch:
    author_id: uuid.UUID
    score: float


@dataclass(slots=True)
class SearchMixedMatch:
    result_type: str
    content_id: uuid.UUID | None
    author_id: uuid.UUID | None
    score: float


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_content(
        self,
        *,
        query_text: str,
        content_type: ContentTypeEnum | None,
        sort: SearchSortEnum,
        offset: int,
        limit: int,
    ) -> tuple[list[SearchContentMatch], bool]:
        ts_query = func.websearch_to_tsquery(literal_column("'simple'"), query_text)
        title = func.coalesce(ContentModel.title, literal_column("''"))
        excerpt = func.coalesce(ContentModel.excerpt, literal_column("''"))
        rank = func.ts_rank_cd(ContentModel.search_vector, ts_query)
        score = func.greatest(
            rank + (func.greatest(func.similarity(title, query_text), func.similarity(excerpt, query_text)) * 0.25),
            literal(0.0),
        )
        search_match = or_(
            ContentModel.search_vector.op("@@")(ts_query),
            title.bool_op("%")(query_text),
            excerpt.bool_op("%")(query_text),
        )

        stmt = (
            select(
                ContentModel.content_id.label("content_id"),
                score.label("score"),
                func.coalesce(ContentModel.published_at, ContentModel.created_at).label("sort_timestamp"),
            )
            .select_from(ContentModel)
            .outerjoin(VideoPlaybackDetailsModel, VideoPlaybackDetailsModel.content_id == ContentModel.content_id)
            .where(*self._content_visibility_clauses())
            .where(search_match)
        )
        if content_type is not None:
            stmt = stmt.where(ContentModel.content_type == content_type)

        stmt = self._apply_content_sort(stmt, sort=sort, score=score)

        result = await self._session.execute(
            stmt.offset(offset).limit(limit + 1)
        )
        rows = list(result.all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        return [
            SearchContentMatch(content_id=row.content_id, score=float(row.score or 0.0))
            for row in rows
        ], has_more

    async def search_authors(
        self,
        *,
        query_text: str,
        sort: SearchSortEnum,
        offset: int,
        limit: int,
    ) -> tuple[list[SearchAuthorMatch], bool]:
        ts_query = func.websearch_to_tsquery(literal_column("'simple'"), query_text)
        username = func.coalesce(UserModel.username, literal_column("''"))
        display_name = func.coalesce(UserModel.display_name, literal_column("''"))
        bio = func.coalesce(UserModel.bio, literal_column("''"))
        vector = func.to_tsvector(
            literal_column("'simple'"),
            username + literal(" ") + display_name + literal(" ") + bio,
        )
        rank = func.ts_rank_cd(vector, ts_query)
        score = func.greatest(
            rank + (func.greatest(func.similarity(username, query_text), func.similarity(display_name, query_text)) * 0.25),
            literal(0.0),
        )
        search_match = or_(
            vector.op("@@")(ts_query),
            username.bool_op("%")(query_text),
            display_name.bool_op("%")(query_text),
        )

        stmt = (
            select(
                UserModel.user_id.label("author_id"),
                score.label("score"),
                UserModel.created_at.label("sort_timestamp"),
            )
            .select_from(UserModel)
            .where(search_match)
        )
        stmt = self._apply_author_sort(stmt, sort=sort, score=score)

        result = await self._session.execute(
            stmt.offset(offset).limit(limit + 1)
        )
        rows = list(result.all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        return [
            SearchAuthorMatch(author_id=row.author_id, score=float(row.score or 0.0))
            for row in rows
        ], has_more

    async def search_all(
        self,
        *,
        query_text: str,
        sort: SearchSortEnum,
        offset: int,
        limit: int,
    ) -> tuple[list[SearchMixedMatch], bool]:
        ts_query = func.websearch_to_tsquery(literal_column("'simple'"), query_text)

        title = func.coalesce(ContentModel.title, literal_column("''"))
        excerpt = func.coalesce(ContentModel.excerpt, literal_column("''"))
        content_rank = func.ts_rank_cd(ContentModel.search_vector, ts_query)
        content_score = func.greatest(
            content_rank + (func.greatest(func.similarity(title, query_text), func.similarity(excerpt, query_text)) * 0.25),
            literal(0.0),
        )
        content_match = or_(
            ContentModel.search_vector.op("@@")(ts_query),
            title.bool_op("%")(query_text),
            excerpt.bool_op("%")(query_text),
        )

        content_select = (
            select(
                literal("content").label("result_type"),
                ContentModel.content_id.label("content_id"),
                literal(None, type_=PGUUID(as_uuid=True)).label("author_id"),
                content_score.label("score"),
                func.coalesce(ContentModel.published_at, ContentModel.created_at).label("sort_timestamp"),
            )
            .select_from(ContentModel)
            .outerjoin(VideoPlaybackDetailsModel, VideoPlaybackDetailsModel.content_id == ContentModel.content_id)
            .where(*self._content_visibility_clauses())
            .where(content_match)
        )

        username = func.coalesce(UserModel.username, literal_column("''"))
        display_name = func.coalesce(UserModel.display_name, literal_column("''"))
        bio = func.coalesce(UserModel.bio, literal_column("''"))
        author_vector = func.to_tsvector(
            literal_column("'simple'"),
            username + literal(" ") + display_name + literal(" ") + bio,
        )
        author_rank = func.ts_rank_cd(author_vector, ts_query)
        author_score = func.greatest(
            author_rank + (func.greatest(func.similarity(username, query_text), func.similarity(display_name, query_text)) * 0.25),
            literal(0.0),
        )
        author_match = or_(
            author_vector.op("@@")(ts_query),
            username.bool_op("%")(query_text),
            display_name.bool_op("%")(query_text),
        )

        author_select = (
            select(
                literal("author").label("result_type"),
                literal(None, type_=PGUUID(as_uuid=True)).label("content_id"),
                UserModel.user_id.label("author_id"),
                author_score.label("score"),
                UserModel.created_at.label("sort_timestamp"),
            )
            .select_from(UserModel)
            .where(author_match)
        )

        merged = content_select.union_all(author_select).subquery()
        stmt = select(merged)

        if sort == SearchSortEnum.NEWEST:
            stmt = stmt.order_by(desc(merged.c.sort_timestamp).nullslast(), desc(merged.c.score))
        elif sort == SearchSortEnum.OLDEST:
            stmt = stmt.order_by(merged.c.sort_timestamp.asc().nullslast(), desc(merged.c.score))
        else:
            stmt = stmt.order_by(desc(merged.c.score), desc(merged.c.sort_timestamp).nullslast())

        result = await self._session.execute(stmt.offset(offset).limit(limit + 1))
        rows = list(result.all())
        has_more = len(rows) > limit
        rows = rows[:limit]

        return [
            SearchMixedMatch(
                result_type=row.result_type,
                content_id=row.content_id,
                author_id=row.author_id,
                score=float(row.score or 0.0),
            )
            for row in rows
        ], has_more

    async def get_content_by_ids(
        self,
        *,
        content_ids: list[uuid.UUID],
        viewer_id: uuid.UUID | None,
    ) -> dict[uuid.UUID, ContentModel]:
        if not content_ids:
            return {}

        query = (
            self._build_content_query(viewer_id=viewer_id)
            .where(ContentModel.content_id.in_(content_ids))
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

    def _content_visibility_clauses(self):
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

    def _apply_content_sort(self, stmt, *, sort: SearchSortEnum, score):  # type: ignore[no-untyped-def]
        sort_timestamp = func.coalesce(ContentModel.published_at, ContentModel.created_at)
        if sort == SearchSortEnum.NEWEST:
            return stmt.order_by(desc(sort_timestamp), desc(score))
        if sort == SearchSortEnum.OLDEST:
            return stmt.order_by(sort_timestamp.asc(), desc(score))
        return stmt.order_by(desc(score), desc(sort_timestamp), desc(ContentModel.created_at))

    def _apply_author_sort(self, stmt, *, sort: SearchSortEnum, score):  # type: ignore[no-untyped-def]
        if sort == SearchSortEnum.NEWEST:
            return stmt.order_by(desc(UserModel.created_at), desc(score), desc(UserModel.subscribers_count))
        if sort == SearchSortEnum.OLDEST:
            return stmt.order_by(UserModel.created_at.asc(), desc(score), desc(UserModel.subscribers_count))
        return stmt.order_by(desc(score), desc(UserModel.subscribers_count), desc(UserModel.created_at))
