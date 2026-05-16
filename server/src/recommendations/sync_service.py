from __future__ import annotations

import datetime
import logging
import uuid
from dataclasses import dataclass

from src.activity.enums import ActivityActionTypeEnum
from src.content.enums import ReactionTypeEnum
from src.recommendations.enums import RecommendationSyncMode
from src.recommendations.graph_repository import RecommendationGraphRepository
from src.recommendations.postgres_repository import (
    ActivityEventGraphRow,
    ContentGraphRow,
    RecommendationPostgresRepository,
)
from src.recommendations.scoring import compute_content_quality_score


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SyncRunReport:
    mode: RecommendationSyncMode
    users: int = 0
    subscriptions: int = 0
    content: int = 0
    content_tags: int = 0
    reactions: int = 0
    views: int = 0
    comments: int = 0
    events: int = 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "users": self.users,
            "subscriptions": self.subscriptions,
            "content": self.content,
            "content_tags": self.content_tags,
            "reactions": self.reactions,
            "views": self.views,
            "comments": self.comments,
            "events": self.events,
        }


class RecommendationGraphSyncService:
    def __init__(
        self,
        *,
        postgres_repository: RecommendationPostgresRepository,
        graph_repository: RecommendationGraphRepository,
        incremental_batch_size: int = 2000,
    ) -> None:
        self._postgres_repository = postgres_repository
        self._graph_repository = graph_repository
        self._incremental_batch_size = incremental_batch_size

    async def full_rebuild(self) -> dict:
        report = SyncRunReport(mode=RecommendationSyncMode.FULL_REBUILD)

        await self._graph_repository.clear_graph()
        await self._graph_repository.ensure_schema()

        user_ids = await self._postgres_repository.get_all_user_ids()
        await self._graph_repository.upsert_users(user_ids)
        report.users = len(user_ids)

        subscriptions = await self._postgres_repository.get_all_subscriptions()
        await self._graph_repository.upsert_subscriptions(subscriptions)
        report.subscriptions = len(subscriptions)

        content_rows = await self._postgres_repository.get_all_content_nodes()
        await self._sync_content_nodes(content_rows)
        report.content = len(content_rows)

        content_tags = await self._postgres_repository.get_all_content_tags()
        await self._graph_repository.replace_content_tags(
            content_ids=[row.content_id for row in content_rows],
            tag_rows=[
                {
                    "content_id": str(row.content_id),
                    "tag_id": str(row.tag_id),
                    "tag_slug": row.tag_slug,
                }
                for row in content_tags
            ],
        )
        report.content_tags = len(content_tags)

        reactions = await self._postgres_repository.get_all_content_reactions()
        await self._graph_repository.clear_reactions()
        await self._graph_repository.set_liked_edges(
            rows=[
                {
                    "user_id": str(row.user_id),
                    "content_id": str(row.content_id),
                    "created_at": self._datetime_to_iso(row.created_at),
                }
                for row in reactions
                if row.reaction_type == ReactionTypeEnum.LIKE
            ]
        )
        await self._graph_repository.set_disliked_edges(
            rows=[
                {
                    "user_id": str(row.user_id),
                    "content_id": str(row.content_id),
                    "created_at": self._datetime_to_iso(row.created_at),
                }
                for row in reactions
                if row.reaction_type == ReactionTypeEnum.DISLIKE
            ]
        )
        report.reactions = len(reactions)

        views = await self._postgres_repository.get_all_content_views()
        await self._graph_repository.clear_viewed_edges()
        await self._graph_repository.set_viewed_edges(
            rows=[
                {
                    "user_id": str(row.user_id),
                    "content_id": str(row.content_id),
                    "views_count": row.views_count,
                    "last_seen_at": self._datetime_to_iso(row.last_seen_at),
                }
                for row in views
            ]
        )
        report.views = len(views)

        comments = await self._postgres_repository.get_all_content_comments()
        await self._graph_repository.clear_commented_edges()
        await self._graph_repository.set_commented_edges(
            rows=[
                {
                    "user_id": str(row.user_id),
                    "content_id": str(row.content_id),
                    "comments_count": row.comments_count,
                    "last_commented_at": self._datetime_to_iso(row.last_commented_at),
                }
                for row in comments
            ]
        )
        report.comments = len(comments)

        await self._graph_repository.recompute_interested_in()
        await self._graph_repository.recompute_affinity_to_author()
        await self._graph_repository.recompute_similar_to()

        latest_activity_cursor = await self._postgres_repository.get_latest_activity_cursor()
        now = datetime.datetime.now(datetime.timezone.utc)
        await self._graph_repository.upsert_sync_state(
            last_event_at=latest_activity_cursor.created_at if latest_activity_cursor is not None else None,
            last_event_id=latest_activity_cursor.activity_event_id if latest_activity_cursor is not None else None,
            last_full_rebuild_at=now,
        )

        return report.to_dict()

    async def incremental_sync(self) -> dict:
        report = SyncRunReport(mode=RecommendationSyncMode.INCREMENTAL_SYNC)

        await self._graph_repository.ensure_schema()
        state = await self._graph_repository.get_sync_state()

        cursor_at = state.last_event_at if state is not None else None
        cursor_id = state.last_event_id if state is not None else None

        touched_user_ids: set[uuid.UUID] = set()
        touched_content_ids: set[uuid.UUID] = set()

        while True:
            events = await self._postgres_repository.get_activity_events_since(
                created_at=cursor_at,
                activity_event_id=cursor_id,
                limit=self._incremental_batch_size,
            )
            if not events:
                break

            report.events += len(events)
            (
                liked_rows,
                disliked_rows,
                remove_liked_rows,
                remove_disliked_rows,
                viewed_rows,
                commented_rows,
                followed_rows,
                unfollowed_rows,
            ) = self._map_events_to_graph_updates(events)

            if followed_rows:
                await self._graph_repository.upsert_subscriptions(followed_rows)
            if unfollowed_rows:
                await self._graph_repository.remove_follow_edges(
                    [
                        {
                            "user_id": str(user_id),
                            "target_user_id": str(target_user_id),
                        }
                        for user_id, target_user_id in unfollowed_rows
                    ]
                )

            if liked_rows:
                await self._graph_repository.set_liked_edges(liked_rows)
            if disliked_rows:
                await self._graph_repository.set_disliked_edges(disliked_rows)
            if remove_liked_rows:
                await self._graph_repository.remove_liked_edges(remove_liked_rows)
            if remove_disliked_rows:
                await self._graph_repository.remove_disliked_edges(remove_disliked_rows)

            if viewed_rows:
                await self._graph_repository.increment_viewed_edges(viewed_rows)
            if commented_rows:
                await self._graph_repository.increment_commented_edges(commented_rows)

            for event in events:
                touched_user_ids.add(event.user_id)
                if event.target_user_id is not None:
                    touched_user_ids.add(event.target_user_id)
                if event.content_id is not None:
                    touched_content_ids.add(event.content_id)

            report.reactions += len(liked_rows) + len(disliked_rows) + len(remove_liked_rows) + len(remove_disliked_rows)
            report.views += len(viewed_rows)
            report.comments += len(commented_rows)
            report.subscriptions += len(followed_rows) + len(unfollowed_rows)

            last_event = events[-1]
            cursor_at = last_event.created_at
            cursor_id = last_event.activity_event_id

        if touched_user_ids:
            existing_user_ids = await self._postgres_repository.get_user_ids_by_ids(list(touched_user_ids))
            await self._graph_repository.upsert_users(existing_user_ids)
            report.users = len(existing_user_ids)

        if touched_content_ids:
            content_rows = await self._postgres_repository.get_content_nodes_by_ids(list(touched_content_ids))
            await self._sync_content_nodes(content_rows)
            report.content = len(content_rows)

            tags = await self._postgres_repository.get_content_tags_by_content_ids(
                [row.content_id for row in content_rows]
            )
            await self._graph_repository.replace_content_tags(
                content_ids=[row.content_id for row in content_rows],
                tag_rows=[
                    {
                        "content_id": str(row.content_id),
                        "tag_id": str(row.tag_id),
                        "tag_slug": row.tag_slug,
                    }
                    for row in tags
                ],
            )
            report.content_tags = len(tags)

        if touched_user_ids:
            await self._graph_repository.recompute_interested_in(list(touched_user_ids))
            await self._graph_repository.recompute_affinity_to_author(list(touched_user_ids))

        if touched_content_ids:
            await self._graph_repository.recompute_similar_to(list(touched_content_ids))

        await self._graph_repository.upsert_sync_state(
            last_event_at=cursor_at,
            last_event_id=cursor_id,
            last_full_rebuild_at=(state.last_full_rebuild_at if state is not None else None),
        )

        return report.to_dict()

    async def _sync_content_nodes(self, content_rows: list[ContentGraphRow]) -> None:
        await self._graph_repository.upsert_content_nodes(
            rows=[
                {
                    "content_id": str(row.content_id),
                    "author_id": str(row.author_id),
                    "content_type": row.content_type.value,
                    "status": row.status.value,
                    "visibility": row.visibility.value,
                    "created_at": self._datetime_to_iso(row.created_at),
                    "published_at": self._datetime_to_iso(row.published_at),
                    "likes_count": row.likes_count,
                    "dislikes_count": row.dislikes_count,
                    "comments_count": row.comments_count,
                    "views_count": row.views_count,
                    "quality_score": compute_content_quality_score(
                        likes_count=row.likes_count,
                        dislikes_count=row.dislikes_count,
                        comments_count=row.comments_count,
                        views_count=row.views_count,
                    ),
                }
                for row in content_rows
            ]
        )
        await self._graph_repository.upsert_authored_edges(
            rows=[
                {
                    "user_id": str(row.author_id),
                    "content_id": str(row.content_id),
                }
                for row in content_rows
            ]
        )

    def _map_events_to_graph_updates(
        self,
        events: list[ActivityEventGraphRow],
    ) -> tuple[
        list[dict[str, str | None]],
        list[dict[str, str | None]],
        list[dict[str, str]],
        list[dict[str, str]],
        list[dict[str, str | int | None]],
        list[dict[str, str | int | None]],
        list[tuple[uuid.UUID, uuid.UUID]],
        list[tuple[uuid.UUID, uuid.UUID]],
    ]:
        liked_rows: list[dict[str, str | None]] = []
        disliked_rows: list[dict[str, str | None]] = []
        remove_liked_rows: list[dict[str, str]] = []
        remove_disliked_rows: list[dict[str, str]] = []
        viewed_rows: list[dict[str, str | int | None]] = []
        commented_rows: list[dict[str, str | int | None]] = []
        followed_rows: list[tuple[uuid.UUID, uuid.UUID]] = []
        unfollowed_rows: list[tuple[uuid.UUID, uuid.UUID]] = []

        for event in events:
            if event.action_type == ActivityActionTypeEnum.CONTENT_VIEW.value and event.content_id is not None:
                viewed_rows.append(
                    {
                        "user_id": str(event.user_id),
                        "content_id": str(event.content_id),
                        "views_count": 1,
                        "last_seen_at": self._datetime_to_iso(event.created_at),
                    }
                )
                continue

            if event.action_type == ActivityActionTypeEnum.CONTENT_LIKE.value and event.content_id is not None:
                liked_rows.append(
                    {
                        "user_id": str(event.user_id),
                        "content_id": str(event.content_id),
                        "created_at": self._datetime_to_iso(event.created_at),
                    }
                )
                continue

            if event.action_type == ActivityActionTypeEnum.CONTENT_DISLIKE.value and event.content_id is not None:
                disliked_rows.append(
                    {
                        "user_id": str(event.user_id),
                        "content_id": str(event.content_id),
                        "created_at": self._datetime_to_iso(event.created_at),
                    }
                )
                continue

            if event.action_type == ActivityActionTypeEnum.CONTENT_REACTION_REMOVED.value and event.content_id is not None:
                previous = str(event.metadata.get("previous_reaction") or "").lower()
                if previous == ReactionTypeEnum.LIKE.value:
                    remove_liked_rows.append(
                        {
                            "user_id": str(event.user_id),
                            "content_id": str(event.content_id),
                        }
                    )
                elif previous == ReactionTypeEnum.DISLIKE.value:
                    remove_disliked_rows.append(
                        {
                            "user_id": str(event.user_id),
                            "content_id": str(event.content_id),
                        }
                    )
                continue

            if event.action_type == ActivityActionTypeEnum.CONTENT_COMMENT.value and event.content_id is not None:
                commented_rows.append(
                    {
                        "user_id": str(event.user_id),
                        "content_id": str(event.content_id),
                        "comments_count": 1,
                        "last_commented_at": self._datetime_to_iso(event.created_at),
                    }
                )
                continue

            if event.action_type == ActivityActionTypeEnum.USER_FOLLOW.value and event.target_user_id is not None:
                followed_rows.append((event.user_id, event.target_user_id))
                continue

            if event.action_type == ActivityActionTypeEnum.USER_UNFOLLOW.value and event.target_user_id is not None:
                unfollowed_rows.append((event.user_id, event.target_user_id))
                continue

        return (
            liked_rows,
            disliked_rows,
            remove_liked_rows,
            remove_disliked_rows,
            viewed_rows,
            commented_rows,
            followed_rows,
            unfollowed_rows,
        )

    @staticmethod
    def _datetime_to_iso(value: datetime.datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc).isoformat()
