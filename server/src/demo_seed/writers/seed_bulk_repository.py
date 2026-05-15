from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import case, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.models import ActivityEventModel
from src.articles.models import ArticleDetailsModel
from src.assets.models import AssetModel, AssetVariantModel, ContentAssetModel, MessageAssetModel
from src.chats.models import ChatModel, ChatTimelineItemModel, MembershipModel
from src.comments.models import CommentModel, CommentReactionModel
from src.content.models import ContentModel, ContentReactionModel, ContentViewSessionModel
from src.events.models import EventModel
from src.messages.models import MessageModel, MessageReactionModel, MessageSharedContentModel
from src.moments.models import MomentDetailsModel
from src.posts.models import PostDetailsModel
from src.tags.models import ContentTagModel, TagModel
from src.users.models import SubscriptionModel, UserModel
from src.videos.models import VideoDetailsModel, VideoPlaybackDetailsModel


class SeedBulkRepository:
    _MAX_QUERY_ARGS = 32000

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def flush_chunks(self, model, rows: Sequence[dict], chunk_size: int = 2000) -> None:  # type: ignore[no-untyped-def]
        if not rows:
            return

        max_params_per_row = max(len(row) for row in rows)
        safe_chunk_size = chunk_size
        if max_params_per_row > 0:
            safe_chunk_size = min(chunk_size, max(1, self._MAX_QUERY_ARGS // max_params_per_row))

        for index in range(0, len(rows), safe_chunk_size):
            chunk = rows[index:index + safe_chunk_size]
            await self._session.execute(insert(model).values(chunk))

    async def upsert_tags(self, slugs: list[str]) -> dict[str, uuid.UUID]:
        existing_rows = await self._session.execute(select(TagModel.tag_id, TagModel.slug).where(TagModel.slug.in_(slugs)))
        mapping = {slug: tag_id for tag_id, slug in existing_rows.all()}
        missing = [slug for slug in slugs if slug not in mapping]
        if missing:
            await self.flush_chunks(
                TagModel,
                [{"slug": slug} for slug in missing],
                chunk_size=500,
            )
            await self._session.flush()
            existing_rows = await self._session.execute(select(TagModel.tag_id, TagModel.slug).where(TagModel.slug.in_(slugs)))
            mapping = {slug: tag_id for tag_id, slug in existing_rows.all()}
        return mapping

    async def insert_users(self, rows: list[dict]) -> None:
        await self.flush_chunks(UserModel, rows, chunk_size=500)

    async def update_user_avatar(
        self,
        user_id: uuid.UUID,
        avatar_asset_id: uuid.UUID,
        avatar_crop: dict | None = None,
    ) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.user_id == user_id)
            .values(
                avatar_asset_id=avatar_asset_id,
                avatar_crop=avatar_crop,
            )
        )

    async def insert_assets(self, rows: list[dict]) -> None:
        await self.flush_chunks(AssetModel, rows, chunk_size=500)

    async def insert_asset_variants(self, rows: list[dict]) -> None:
        await self.flush_chunks(AssetVariantModel, rows, chunk_size=1000)

    async def insert_content(self, rows: list[dict]) -> None:
        await self.flush_chunks(ContentModel, rows, chunk_size=500)

    async def insert_post_details(self, rows: list[dict]) -> None:
        await self.flush_chunks(PostDetailsModel, rows, chunk_size=1000)

    async def insert_article_details(self, rows: list[dict]) -> None:
        await self.flush_chunks(ArticleDetailsModel, rows, chunk_size=500)

    async def insert_video_details(self, rows: list[dict]) -> None:
        await self.flush_chunks(VideoDetailsModel, rows, chunk_size=500)

    async def insert_moment_details(self, rows: list[dict]) -> None:
        await self.flush_chunks(MomentDetailsModel, rows, chunk_size=500)

    async def insert_video_playback_details(self, rows: list[dict]) -> None:
        await self.flush_chunks(VideoPlaybackDetailsModel, rows, chunk_size=500)

    async def insert_content_tags(self, rows: list[dict]) -> None:
        await self.flush_chunks(ContentTagModel, rows, chunk_size=2000)

    async def insert_content_assets(self, rows: list[dict]) -> None:
        await self.flush_chunks(ContentAssetModel, rows, chunk_size=2000)

    async def insert_subscriptions(self, rows: list[dict]) -> None:
        await self.flush_chunks(SubscriptionModel, rows, chunk_size=3000)

    async def insert_content_reactions(self, rows: list[dict]) -> None:
        await self.flush_chunks(ContentReactionModel, rows, chunk_size=4000)

    async def insert_comments(self, rows: list[dict]) -> None:
        await self.flush_chunks(CommentModel, rows, chunk_size=2000)

    async def insert_comment_reactions(self, rows: list[dict]) -> None:
        await self.flush_chunks(CommentReactionModel, rows, chunk_size=3000)

    async def insert_view_sessions(self, rows: list[dict]) -> None:
        await self.flush_chunks(ContentViewSessionModel, rows, chunk_size=3000)

    async def insert_activity_events(self, rows: list[dict]) -> None:
        await self.flush_chunks(ActivityEventModel, rows, chunk_size=4000)

    async def insert_chats(self, rows: list[dict]) -> None:
        await self.flush_chunks(ChatModel, rows, chunk_size=500)

    async def insert_memberships(self, rows: list[dict]) -> None:
        await self.flush_chunks(MembershipModel, rows, chunk_size=2000)

    async def insert_messages(self, rows: list[dict]) -> None:
        await self.flush_chunks(MessageModel, rows, chunk_size=2000)

    async def insert_message_reactions(self, rows: list[dict]) -> None:
        await self.flush_chunks(MessageReactionModel, rows, chunk_size=2000)

    async def insert_message_shared_content(self, rows: list[dict]) -> None:
        await self.flush_chunks(MessageSharedContentModel, rows, chunk_size=1500)

    async def insert_message_assets(self, rows: list[dict]) -> None:
        await self.flush_chunks(MessageAssetModel, rows, chunk_size=2000)

    async def insert_events(self, rows: list[dict]) -> None:
        await self.flush_chunks(EventModel, rows, chunk_size=1000)

    async def insert_timeline_items(self, rows: list[dict]) -> None:
        await self.flush_chunks(ChatTimelineItemModel, rows, chunk_size=3000)

    async def refresh_chat_last_sequence(self) -> None:
        subquery = (
            select(
                ChatTimelineItemModel.chat_id,
                func.max(ChatTimelineItemModel.chat_seq).label("max_seq"),
            )
            .group_by(ChatTimelineItemModel.chat_id)
            .subquery()
        )
        await self._session.execute(
            update(ChatModel)
            .where(ChatModel.chat_id == subquery.c.chat_id)
            .values(last_timeline_seq=subquery.c.max_seq)
        )

    async def reconcile_subscriber_counters(self) -> None:
        subquery = (
            select(
                SubscriptionModel.subscribed_id.label("user_id"),
                func.count().label("count"),
            )
            .group_by(SubscriptionModel.subscribed_id)
            .subquery()
        )
        await self._session.execute(update(UserModel).values(subscribers_count=0))
        await self._session.execute(
            update(UserModel)
            .where(UserModel.user_id == subquery.c.user_id)
            .values(subscribers_count=subquery.c.count)
        )

    async def reconcile_comment_counters(self) -> None:
        content_counts = (
            select(
                CommentModel.content_id,
                func.count().label("comments_count"),
            )
            .where(CommentModel.deleted_at.is_(None))
            .group_by(CommentModel.content_id)
            .subquery()
        )
        await self._session.execute(update(ContentModel).values(comments_count=0))
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_counts.c.content_id)
            .values(comments_count=content_counts.c.comments_count)
        )

        reply_counts = (
            select(
                CommentModel.parent_comment_id,
                func.count().label("replies_count"),
            )
            .where(CommentModel.parent_comment_id.is_not(None))
            .where(CommentModel.deleted_at.is_(None))
            .group_by(CommentModel.parent_comment_id)
            .subquery()
        )
        await self._session.execute(update(CommentModel).values(replies_count=0))
        await self._session.execute(
            update(CommentModel)
            .where(CommentModel.comment_id == reply_counts.c.parent_comment_id)
            .values(replies_count=reply_counts.c.replies_count)
        )

    async def reconcile_reaction_counters(self) -> None:
        reaction_counts = (
            select(
                ContentReactionModel.content_id,
                func.sum(case((ContentReactionModel.reaction_type == "like", 1), else_=0)).label("likes"),
                func.sum(case((ContentReactionModel.reaction_type == "dislike", 1), else_=0)).label("dislikes"),
            )
            .group_by(ContentReactionModel.content_id)
            .subquery()
        )
        await self._session.execute(update(ContentModel).values(likes_count=0, dislikes_count=0))
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == reaction_counts.c.content_id)
            .values(
                likes_count=func.coalesce(reaction_counts.c.likes, 0),
                dislikes_count=func.coalesce(reaction_counts.c.dislikes, 0),
            )
        )

        comment_counts = (
            select(
                CommentReactionModel.comment_id,
                func.sum(case((CommentReactionModel.reaction_type == "like", 1), else_=0)).label("likes"),
                func.sum(case((CommentReactionModel.reaction_type == "dislike", 1), else_=0)).label("dislikes"),
            )
            .group_by(CommentReactionModel.comment_id)
            .subquery()
        )
        await self._session.execute(update(CommentModel).values(likes_count=0, dislikes_count=0))
        await self._session.execute(
            update(CommentModel)
            .where(CommentModel.comment_id == comment_counts.c.comment_id)
            .values(
                likes_count=func.coalesce(comment_counts.c.likes, 0),
                dislikes_count=func.coalesce(comment_counts.c.dislikes, 0),
            )
        )

    async def reconcile_views_counters(self) -> None:
        views_counts = (
            select(
                ContentViewSessionModel.content_id,
                func.count().label("count"),
            )
            .where(ContentViewSessionModel.is_counted.is_(True))
            .group_by(ContentViewSessionModel.content_id)
            .subquery()
        )
        await self._session.execute(update(ContentModel).values(views_count=0))
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == views_counts.c.content_id)
            .values(views_count=views_counts.c.count)
        )

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
