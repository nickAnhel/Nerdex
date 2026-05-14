from __future__ import annotations

import datetime
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.activity.enums import ActivityActionTypeEnum, ActivityPeriodEnum
from src.activity.models import ActivityEventModel
from src.assets.models import AssetModel, ContentAssetModel
from src.comments.models import CommentModel
from src.content.enums import ContentTypeEnum, ReactionTypeEnum
from src.content.models import ContentModel, ContentReactionModel
from src.users.models import UserModel


class ActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(
        self,
        *,
        user_id: uuid.UUID,
        action_type: ActivityActionTypeEnum,
        content_id: uuid.UUID | None = None,
        target_user_id: uuid.UUID | None = None,
        comment_id: uuid.UUID | None = None,
        content_type: ContentTypeEnum | None = None,
        metadata: dict | None = None,
        created_at: datetime.datetime | None = None,
        commit: bool = True,
    ) -> ActivityEventModel:
        event = ActivityEventModel(
            activity_event_id=uuid.uuid4(),
            user_id=user_id,
            action_type=action_type,
            content_id=content_id,
            target_user_id=target_user_id,
            comment_id=comment_id,
            content_type=content_type,
            event_metadata=metadata or {},
            created_at=created_at or datetime.datetime.now(datetime.timezone.utc),
        )
        self._session.add(event)
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()
        return event

    async def get_user_activity(
        self,
        *,
        user_id: uuid.UUID,
        action_types: list[ActivityActionTypeEnum] | None = None,
        content_type: ContentTypeEnum | None = None,
        period: ActivityPeriodEnum = ActivityPeriodEnum.ALL_TIME,
        offset: int,
        limit: int,
    ) -> tuple[list[ActivityEventModel], bool]:
        stmt = (
            select(ActivityEventModel)
            .where(ActivityEventModel.user_id == user_id)
            .options(
                selectinload(ActivityEventModel.target_user)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
                selectinload(ActivityEventModel.comment),
                selectinload(ActivityEventModel.content).selectinload(ContentModel.author).selectinload(UserModel.subscribers),
                selectinload(ActivityEventModel.content)
                .selectinload(ContentModel.author)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
                selectinload(ActivityEventModel.content).selectinload(ContentModel.post_details),
                selectinload(ActivityEventModel.content).selectinload(ContentModel.article_details),
                selectinload(ActivityEventModel.content).selectinload(ContentModel.video_details),
                selectinload(ActivityEventModel.content).selectinload(ContentModel.moment_details),
                selectinload(ActivityEventModel.content).selectinload(ContentModel.video_playback_details),
                selectinload(ActivityEventModel.content).selectinload(ContentModel.tags),
                selectinload(ActivityEventModel.content)
                .selectinload(ContentModel.asset_links)
                .selectinload(ContentAssetModel.asset)
                .selectinload(AssetModel.variants),
            )
            .order_by(desc(ActivityEventModel.created_at))
            .offset(offset)
            .limit(limit + 1)
        )
        if action_types:
            stmt = stmt.where(ActivityEventModel.action_type.in_(action_types))
        if content_type is not None:
            stmt = stmt.where(ActivityEventModel.content_type == content_type)

        since = self._period_since(period)
        if since is not None:
            stmt = stmt.where(ActivityEventModel.created_at >= since)

        result = await self._session.execute(stmt)
        events = list(result.scalars().unique().all())
        has_more = len(events) > limit
        events = events[:limit]
        await self.populate_content_reactions(events=events, viewer_id=user_id)
        return events, has_more

    async def populate_content_reactions(
        self,
        *,
        events: list[ActivityEventModel],
        viewer_id: uuid.UUID,
    ) -> None:
        contents = [event.content for event in events if event.content is not None]
        content_ids = [content.content_id for content in contents]
        if not content_ids:
            return

        result = await self._session.execute(
            select(ContentReactionModel.content_id, ContentReactionModel.reaction_type)
            .where(ContentReactionModel.user_id == viewer_id)
            .where(ContentReactionModel.content_id.in_(content_ids))
        )
        reactions: dict[uuid.UUID, ReactionTypeEnum] = {
            content_id: reaction_type
            for content_id, reaction_type in result.all()
        }
        for content in contents:
            content.my_reaction = reactions.get(content.content_id)
            content.is_owner = content.author_id == viewer_id

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    def _period_since(self, period: ActivityPeriodEnum) -> datetime.datetime | None:
        now = datetime.datetime.now(datetime.timezone.utc)
        if period == ActivityPeriodEnum.WEEK:
            return now - datetime.timedelta(days=7)
        if period == ActivityPeriodEnum.MONTH:
            return now - datetime.timedelta(days=30)
        if period == ActivityPeriodEnum.YEAR:
            return now - datetime.timedelta(days=365)
        return None
