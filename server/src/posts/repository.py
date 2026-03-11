from __future__ import annotations

import datetime
import uuid

from sqlalchemy import delete, desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import src.tags.models  # noqa: F401
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.models import ContentModel, ContentReactionModel
from src.posts.enums import PostOrder, PostProfileFilter
from src.posts.models import PostDetailsModel
from src.users.models import SubscriptionModel


class PostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        author_id: uuid.UUID,
        body_text: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        created_at: datetime.datetime,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        commit: bool = True,
    ) -> ContentModel:
        stmt = (
            insert(ContentModel)
            .values(
                author_id=author_id,
                content_type=ContentTypeEnum.POST,
                status=status,
                visibility=visibility,
                created_at=created_at,
                updated_at=updated_at,
                published_at=published_at,
            )
            .returning(ContentModel.content_id)
        )
        result = await self._session.execute(stmt)
        content_id = result.scalar_one()

        await self._session.execute(
            insert(PostDetailsModel).values(
                content_id=content_id,
                body_text=body_text,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_single(content_id=content_id)

    async def get_single(
        self,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
    ) -> ContentModel | None:
        stmt = self._build_post_query(viewer_id=viewer_id).where(ContentModel.content_id == content_id)
        result = await self._session.execute(stmt)
        return self._one_or_none(result, viewer_id=viewer_id)

    async def get_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_post_query(viewer_id=viewer_id)
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def get_author_posts(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        profile_filter: PostProfileFilter,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_post_query(viewer_id=viewer_id)
            .where(ContentModel.author_id == author_id)
            .where(ContentModel.deleted_at.is_(None))
        )

        if viewer_id == author_id:
            if profile_filter == PostProfileFilter.ALL:
                stmt = stmt.where(
                    ContentModel.status.in_(
                        [ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT]
                    )
                )
            elif profile_filter == PostProfileFilter.DRAFTS:
                stmt = stmt.where(ContentModel.status == ContentStatusEnum.DRAFT)
            elif profile_filter == PostProfileFilter.PRIVATE:
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

    async def get_user_subscriptions_posts(
        self,
        *,
        user_id: uuid.UUID,
        order: PostOrder,
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
            self._build_post_query(viewer_id=user_id)
            .where(ContentModel.author_id.in_(select(subs_subquery.c.subscribed_id)))
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=user_id)

    async def update_post(
        self,
        *,
        content_id: uuid.UUID,
        body_text: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        commit: bool = True,
    ) -> ContentModel:
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(
                status=status,
                visibility=visibility,
                updated_at=updated_at,
                published_at=published_at,
            )
        )
        await self._session.execute(
            update(PostDetailsModel)
            .where(PostDetailsModel.content_id == content_id)
            .values(body_text=body_text)
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_single(content_id=content_id)

    async def commit(self) -> None:
        await self._session.commit()

    async def soft_delete_post(
        self,
        *,
        content_id: uuid.UUID,
        updated_at: datetime.datetime,
        deleted_at: datetime.datetime,
    ) -> ContentModel:
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(
                status=ContentStatusEnum.DELETED,
                deleted_at=deleted_at,
                updated_at=updated_at,
            )
        )
        await self._session.commit()
        return await self.get_single(content_id=content_id)

    async def set_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
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
            return

        if existing.reaction_type == reaction_type:
            return

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

    async def remove_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        existing = await self._get_reaction(content_id=content_id, user_id=user_id)
        if existing is None or existing.reaction_type != reaction_type:
            return

        await self._session.execute(
            delete(ContentReactionModel)
            .where(ContentReactionModel.content_id == content_id)
            .where(ContentReactionModel.user_id == user_id)
        )
        await self._update_reaction_counters(
            content_id=content_id,
            like_delta=-1 if reaction_type == ReactionTypeEnum.LIKE else 0,
            dislike_delta=-1 if reaction_type == ReactionTypeEnum.DISLIKE else 0,
        )
        await self._session.commit()

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

    def _build_post_query(self, viewer_id: uuid.UUID | None):
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)

        if reaction_subquery is None:
            return (
                select(ContentModel)
                .where(ContentModel.content_type == ContentTypeEnum.POST)
                .options(
                    selectinload(ContentModel.author),
                    selectinload(ContentModel.post_details),
                    selectinload(ContentModel.tags),
                )
            )

        return (
            select(
                ContentModel,
                reaction_subquery.c.reaction_type.label("my_reaction"),
            )
            .outerjoin(
                reaction_subquery,
                ContentModel.content_id == reaction_subquery.c.content_id,
            )
            .where(ContentModel.content_type == ContentTypeEnum.POST)
            .options(
                selectinload(ContentModel.author),
                selectinload(ContentModel.post_details),
                selectinload(ContentModel.tags),
            )
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
            posts = list(result.scalars().unique().all())
            for post in posts:
                post.my_reaction = None
                post.is_owner = False
            return posts

        posts: list[ContentModel] = []
        for post, my_reaction in result.unique().all():
            post.my_reaction = my_reaction
            post.is_owner = post.author_id == viewer_id
            posts.append(post)
        return posts

    def _one_or_none(self, result, viewer_id: uuid.UUID | None) -> ContentModel | None:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            post = result.scalar_one_or_none()
            if post is not None:
                post.my_reaction = None
                post.is_owner = False
            return post

        row = result.one_or_none()
        if row is None:
            return None

        post, my_reaction = row
        post.my_reaction = my_reaction
        post.is_owner = post.author_id == viewer_id
        return post

    def _order_by_clause(self, order: PostOrder, order_desc: bool):
        order_mapping = {
            PostOrder.ID: ContentModel.content_id,
            PostOrder.CREATED_AT: ContentModel.created_at,
            PostOrder.UPDATED_AT: ContentModel.updated_at,
            PostOrder.PUBLISHED_AT: ContentModel.published_at,
        }
        column = order_mapping[order]
        return desc(column) if order_desc else column
