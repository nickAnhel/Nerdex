from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Executable

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
from src.tags.models import ContentTagModel
from src.users.models import SubscriptionModel, UserModel
from src.videos.models import VideoDetailsModel, VideoPlaybackDetailsModel

T = TypeVar("T")


def _iter_chunks(values: list[T], chunk_size: int) -> Iterable[list[T]]:
    for index in range(0, len(values), chunk_size):
        yield values[index:index + chunk_size]


class SeedCleanupRepository:
    _ID_CHUNK_SIZE = 10000

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _sum_chunked_rowcount(
        self,
        ids: list,
        statement_factory: Callable[[list], Executable],
    ) -> int:
        total = 0
        for chunk in _iter_chunks(ids, self._ID_CHUNK_SIZE):
            result = await self._session.execute(statement_factory(chunk))
            total += int(result.rowcount or 0)
        return total

    async def _list_variant_keys(self, asset_ids: list) -> list[tuple[str, str]]:
        variant_keys: list[tuple[str, str]] = []
        for chunk in _iter_chunks(asset_ids, self._ID_CHUNK_SIZE):
            variant_rows = await self._session.execute(
                select(AssetVariantModel.storage_bucket, AssetVariantModel.storage_key)
                .where(AssetVariantModel.asset_id.in_(chunk))
            )
            variant_keys.extend((row[0], row[1]) for row in variant_rows.all())
        return variant_keys

    async def find_scope(self, seed_run_id: str) -> dict[str, list]:
        marker = f"[seed_run_id={seed_run_id}]"
        user_ids = [
            row[0] for row in (
                await self._session.execute(
                    select(UserModel.user_id)
                    .where(UserModel.username.like("demo_%"))
                    .where(UserModel.bio.contains(marker))
                )
            ).all()
        ]
        content_seed_run_id_expr = ContentModel.content_metadata["seed_run_id"].as_string()
        content_ids = [
            row[0] for row in (
                await self._session.execute(
                    select(ContentModel.content_id)
                    .where(content_seed_run_id_expr == seed_run_id)
                )
            ).all()
        ]
        asset_seed_run_id_expr = AssetModel.asset_metadata["seed_run_id"].as_string()
        asset_ids = [
            row[0] for row in (
                await self._session.execute(
                    select(AssetModel.asset_id)
                    .where(asset_seed_run_id_expr == seed_run_id)
                )
            ).all()
        ]
        chat_ids = [
            row[0] for row in (
                await self._session.execute(
                    select(ChatModel.chat_id)
                    .where(ChatModel.title.like(f"[DEMO:{seed_run_id}]%"))
                )
            ).all()
        ]
        variant_keys: list[tuple[str, str]] = []
        if asset_ids:
            variant_keys = await self._list_variant_keys(asset_ids)

        return {
            "user_ids": user_ids,
            "content_ids": content_ids,
            "asset_ids": asset_ids,
            "chat_ids": chat_ids,
            "variant_keys": variant_keys,
        }

    async def cleanup_scope(self, scope: dict[str, list]) -> dict[str, int]:
        content_ids = scope["content_ids"]
        asset_ids = scope["asset_ids"]
        user_ids = scope["user_ids"]
        chat_ids = scope["chat_ids"]
        counts: dict[str, int] = {}

        def _count(key: str, affected: int | None) -> None:
            counts[key] = int(affected or 0)

        if chat_ids:
            _count(
                "message_reactions",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(MessageReactionModel).where(
                        MessageReactionModel.message_id.in_(
                            select(MessageModel.message_id).where(MessageModel.chat_id.in_(chunk))
                        )
                    ),
                ),
            )
            _count(
                "message_assets",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(MessageAssetModel).where(
                        MessageAssetModel.message_id.in_(
                            select(MessageModel.message_id).where(MessageModel.chat_id.in_(chunk))
                        )
                    ),
                ),
            )
            _count(
                "message_shared_content",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(MessageSharedContentModel).where(
                        MessageSharedContentModel.message_id.in_(
                            select(MessageModel.message_id).where(MessageModel.chat_id.in_(chunk))
                        )
                    ),
                ),
            )
            _count(
                "timeline_items",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(ChatTimelineItemModel).where(ChatTimelineItemModel.chat_id.in_(chunk)),
                ),
            )
            _count(
                "events",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(EventModel).where(EventModel.chat_id.in_(chunk)),
                ),
            )
            _count(
                "messages",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(MessageModel).where(MessageModel.chat_id.in_(chunk)),
                ),
            )
            _count(
                "memberships",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(MembershipModel).where(MembershipModel.chat_id.in_(chunk)),
                ),
            )
            _count(
                "chats",
                await self._sum_chunked_rowcount(
                    chat_ids,
                    lambda chunk: delete(ChatModel).where(ChatModel.chat_id.in_(chunk)),
                ),
            )

        if user_ids:
            _count(
                "activity_events",
                await self._sum_chunked_rowcount(
                    user_ids,
                    lambda chunk: delete(ActivityEventModel).where(ActivityEventModel.user_id.in_(chunk)),
                ),
            )

        if content_ids:
            _count(
                "comment_reactions",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(CommentReactionModel).where(
                        CommentReactionModel.comment_id.in_(
                            select(CommentModel.comment_id).where(CommentModel.content_id.in_(chunk))
                        )
                    ),
                ),
            )
            _count(
                "comments",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(CommentModel).where(CommentModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "content_reactions",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(ContentReactionModel).where(ContentReactionModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "view_sessions",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(ContentViewSessionModel).where(ContentViewSessionModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "content_tags",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(ContentTagModel).where(ContentTagModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "content_assets",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(ContentAssetModel).where(ContentAssetModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "post_details",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(PostDetailsModel).where(PostDetailsModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "article_details",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(ArticleDetailsModel).where(ArticleDetailsModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "video_details",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(VideoDetailsModel).where(VideoDetailsModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "moment_details",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(MomentDetailsModel).where(MomentDetailsModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "video_playback_details",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(VideoPlaybackDetailsModel).where(VideoPlaybackDetailsModel.content_id.in_(chunk)),
                ),
            )
            _count(
                "content",
                await self._sum_chunked_rowcount(
                    content_ids,
                    lambda chunk: delete(ContentModel).where(ContentModel.content_id.in_(chunk)),
                ),
            )

        if user_ids:
            _count(
                "subscriptions",
                await self._sum_chunked_rowcount(
                    user_ids,
                    lambda chunk: delete(SubscriptionModel).where(
                        (SubscriptionModel.subscriber_id.in_(chunk)) | (SubscriptionModel.subscribed_id.in_(chunk))
                    ),
                ),
            )

        if asset_ids:
            _count(
                "asset_variants",
                await self._sum_chunked_rowcount(
                    asset_ids,
                    lambda chunk: delete(AssetVariantModel).where(AssetVariantModel.asset_id.in_(chunk)),
                ),
            )
            _count(
                "assets",
                await self._sum_chunked_rowcount(
                    asset_ids,
                    lambda chunk: delete(AssetModel).where(AssetModel.asset_id.in_(chunk)),
                ),
            )

        if user_ids:
            _count(
                "users",
                await self._sum_chunked_rowcount(
                    user_ids,
                    lambda chunk: delete(UserModel).where(UserModel.user_id.in_(chunk)),
                ),
            )

        await self._session.commit()
        return counts
