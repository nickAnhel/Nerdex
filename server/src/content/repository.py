from __future__ import annotations

import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.models import AssetModel, ContentAssetModel
import src.articles.models  # noqa: F401
import src.tags.models  # noqa: F401
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.enums_list import ContentOrder
from src.content.models import ContentModel, ContentReactionModel
from src.users.models import SubscriptionModel, UserModel
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
            .where(ContentModel.content_type.in_([ContentTypeEnum.POST, ContentTypeEnum.ARTICLE]))
            .where(ContentModel.status == ContentStatusEnum.PUBLISHED)
            .where(ContentModel.visibility == ContentVisibilityEnum.PUBLIC)
            .where(ContentModel.deleted_at.is_(None))
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
            .where(ContentModel.content_type.in_([ContentTypeEnum.POST, ContentTypeEnum.ARTICLE]))
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

    def _build_content_query(self, viewer_id: uuid.UUID | None):
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)
        base_options = (
            selectinload(ContentModel.author).selectinload(UserModel.subscribers),
            selectinload(ContentModel.author)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants),
            selectinload(ContentModel.post_details),
            selectinload(ContentModel.article_details),
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

    def _order_by_clause(self, order: ContentOrder, order_desc: bool):
        order_mapping = {
            ContentOrder.ID: ContentModel.content_id,
            ContentOrder.CREATED_AT: ContentModel.created_at,
            ContentOrder.UPDATED_AT: ContentModel.updated_at,
            ContentOrder.PUBLISHED_AT: ContentModel.published_at,
        }
        column = order_mapping[order]
        return desc(column) if order_desc else column
