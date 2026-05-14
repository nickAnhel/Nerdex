from __future__ import annotations

import datetime
import uuid

from sqlalchemy import delete, desc, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.enums import AttachmentTypeEnum
from src.assets.models import AssetModel, ContentAssetModel
import src.tags.models  # noqa: F401
from src.articles.enums import ArticleOrder, ArticleProfileFilter
from src.articles.models import ArticleDetailsModel
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.models import ContentModel, ContentReactionModel
from src.content.repository import ContentReactionRemoveResult, ContentReactionSetResult
from src.users.models import SubscriptionModel, UserModel


ARTICLE_ATTACHMENT_TYPES = (
    AttachmentTypeEnum.COVER,
    AttachmentTypeEnum.INLINE,
    AttachmentTypeEnum.VIDEO_SOURCE,
)


class ArticleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        author_id: uuid.UUID,
        title: str,
        excerpt: str,
        body_markdown: str,
        slug: str,
        word_count: int,
        reading_time_minutes: int,
        toc: list[dict[str, str | int]],
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
                content_type=ContentTypeEnum.ARTICLE,
                status=status,
                visibility=visibility,
                title=title,
                excerpt=excerpt,
                created_at=created_at,
                updated_at=updated_at,
                published_at=published_at,
            )
            .returning(ContentModel.content_id)
        )
        result = await self._session.execute(stmt)
        content_id = result.scalar_one()

        await self._session.execute(
            insert(ArticleDetailsModel).values(
                content_id=content_id,
                slug=slug,
                body_markdown=body_markdown,
                word_count=word_count,
                reading_time_minutes=reading_time_minutes,
                toc=toc,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_single(content_id=content_id)

    async def get_single(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
    ) -> ContentModel | None:
        stmt = self._build_article_query(viewer_id=viewer_id).where(ContentModel.content_id == content_id)
        result = await self._session.execute(stmt)
        return self._one_or_none(result, viewer_id=viewer_id)

    async def get_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        order: ArticleOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_article_query(viewer_id=viewer_id)
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
            .order_by(self._order_by_clause(order=order, order_desc=order_desc))
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return self._many(result, viewer_id=viewer_id)

    async def get_author_articles(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        profile_filter: ArticleProfileFilter,
        order: ArticleOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentModel]:
        stmt = (
            self._build_article_query(viewer_id=viewer_id)
            .where(ContentModel.author_id == author_id)
            .where(ContentModel.deleted_at.is_(None))
        )

        if viewer_id == author_id:
            if profile_filter == ArticleProfileFilter.ALL:
                stmt = stmt.where(
                    ContentModel.status.in_(
                        [ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT]
                    )
                )
            elif profile_filter == ArticleProfileFilter.DRAFTS:
                stmt = stmt.where(ContentModel.status == ContentStatusEnum.DRAFT)
            elif profile_filter == ArticleProfileFilter.PRIVATE:
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

    async def update_article(
        self,
        *,
        content_id: uuid.UUID,
        title: str,
        excerpt: str,
        body_markdown: str,
        slug: str,
        word_count: int,
        reading_time_minutes: int,
        toc: list[dict[str, str | int]],
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
                title=title,
                excerpt=excerpt,
                status=status,
                visibility=visibility,
                updated_at=updated_at,
                published_at=published_at,
            )
        )
        await self._session.execute(
            update(ArticleDetailsModel)
            .where(ArticleDetailsModel.content_id == content_id)
            .values(
                slug=slug,
                body_markdown=body_markdown,
                word_count=word_count,
                reading_time_minutes=reading_time_minutes,
                toc=toc,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_single(content_id=content_id)

    async def commit(self) -> None:
        await self._session.commit()

    async def get_attachment_asset_ids(
        self,
        *,
        content_id: uuid.UUID,
    ) -> set[uuid.UUID]:
        result = await self._session.execute(
            select(ContentAssetModel.asset_id).where(
                ContentAssetModel.content_id == content_id,
                ContentAssetModel.attachment_type.in_(ARTICLE_ATTACHMENT_TYPES),
            )
        )
        return set(result.scalars().all())

    async def replace_asset_links(
        self,
        *,
        content_id: uuid.UUID,
        attachments: list[dict[str, object]],
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            delete(ContentAssetModel).where(
                ContentAssetModel.content_id == content_id,
                ContentAssetModel.attachment_type.in_(ARTICLE_ATTACHMENT_TYPES),
            )
        )
        if attachments:
            await self._session.execute(
                insert(ContentAssetModel),
                [{**attachment, "content_id": content_id} for attachment in attachments],
            )

        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def soft_delete_article(
        self,
        *,
        content_id: uuid.UUID,
        updated_at: datetime.datetime,
        deleted_at: datetime.datetime,
        commit: bool = True,
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
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return await self.get_single(content_id=content_id)

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
        reaction_type: ReactionTypeEnum,
    ) -> ContentReactionRemoveResult:
        existing = await self._get_reaction(content_id=content_id, user_id=user_id)
        if existing is None or existing.reaction_type != reaction_type:
            return ContentReactionRemoveResult(
                removed=False,
                previous_reaction=existing.reaction_type if existing is not None else None,
            )

        previous_reaction = existing.reaction_type
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
        return ContentReactionRemoveResult(removed=True, previous_reaction=previous_reaction)

    async def get_user_subscriptions_articles(
        self,
        *,
        user_id: uuid.UUID,
        order: ArticleOrder,
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
            self._build_article_query(viewer_id=user_id)
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

    def _build_article_query(self, viewer_id: uuid.UUID | None):
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)

        base_options = (
            selectinload(ContentModel.author).selectinload(UserModel.subscribers),
            selectinload(ContentModel.author)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants),
            selectinload(ContentModel.article_details),
            selectinload(ContentModel.tags),
            selectinload(ContentModel.asset_links)
            .selectinload(ContentAssetModel.asset)
            .selectinload(AssetModel.variants),
        )
        if reaction_subquery is None:
            return (
                select(ContentModel)
                .where(ContentModel.content_type == ContentTypeEnum.ARTICLE)
                .options(*base_options)
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
            .where(ContentModel.content_type == ContentTypeEnum.ARTICLE)
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

    def _many(self, result, viewer_id: uuid.UUID | None) -> list[ContentModel]:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            articles = list(result.scalars().unique().all())
            for article in articles:
                article.my_reaction = None
                article.is_owner = False
            return articles

        articles: list[ContentModel] = []
        for article, my_reaction in result.unique().all():
            article.my_reaction = my_reaction
            article.is_owner = article.author_id == viewer_id
            articles.append(article)
        return articles

    def _one_or_none(self, result, viewer_id: uuid.UUID | None) -> ContentModel | None:  # type: ignore[no-untyped-def]
        if viewer_id is None:
            article = result.scalar_one_or_none()
            if article is not None:
                article.my_reaction = None
                article.is_owner = False
            return article

        row = result.one_or_none()
        if row is None:
            return None

        article, my_reaction = row
        article.my_reaction = my_reaction
        article.is_owner = article.author_id == viewer_id
        return article

    def _order_by_clause(self, order: ArticleOrder, order_desc: bool):
        order_mapping = {
            ArticleOrder.ID: ContentModel.content_id,
            ArticleOrder.CREATED_AT: ContentModel.created_at,
            ArticleOrder.UPDATED_AT: ContentModel.updated_at,
            ArticleOrder.PUBLISHED_AT: ContentModel.published_at,
        }
        column = order_mapping[order]
        return desc(column) if order_desc else column
