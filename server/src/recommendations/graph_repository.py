from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Any

from neo4j import AsyncGraphDatabase

from src.config import settings
from src.recommendations.enums import RecommendationSyncStateKey
from src.recommendations.scoring import (
    AUTHOR_AFFINITY_WEIGHT,
    COLLABORATIVE_COMMENT_WEIGHT,
    COLLABORATIVE_LIKE_WEIGHT,
    COLLABORATIVE_VIEW_WEIGHT,
    COLLABORATIVE_WEIGHT,
    CONTENT_QUALITY_WEIGHT,
    FRESHNESS_DECAY_DAYS,
    FRESHNESS_WEIGHT,
    TAG_AFFINITY_WEIGHT,
)


@dataclass(slots=True)
class SimilarContentGraphResult:
    content_id: uuid.UUID
    score: float
    reason: str


@dataclass(slots=True)
class RecommendationFeedGraphResult:
    content_id: uuid.UUID
    score: float
    reason: str


@dataclass(slots=True)
class RecommendationGraphSyncState:
    last_event_at: datetime.datetime | None
    last_event_id: uuid.UUID | None
    last_full_rebuild_at: datetime.datetime | None


def create_neo4j_driver():
    return AsyncGraphDatabase.driver(
        settings.neo4j.uri,
        auth=(settings.neo4j.user, settings.neo4j.password),
    )


class RecommendationGraphRepository:
    def __init__(self, *, driver, database: str) -> None:  # type: ignore[no-untyped-def]
        self._driver = driver
        self._database = database

    async def close(self) -> None:
        await self._driver.close()

    async def clear_graph(self) -> None:
        await self._write("MATCH (n) DETACH DELETE n")

    async def ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT recomm_user_id_unique IF NOT EXISTS FOR (u:User) REQUIRE u.user_id IS UNIQUE",
            "CREATE CONSTRAINT recomm_content_id_unique IF NOT EXISTS FOR (c:Content) REQUIRE c.content_id IS UNIQUE",
            "CREATE CONSTRAINT recomm_tag_id_unique IF NOT EXISTS FOR (t:Tag) REQUIRE t.tag_id IS UNIQUE",
            "CREATE CONSTRAINT recomm_sync_state_unique IF NOT EXISTS FOR (s:RecommendationSyncState) REQUIRE s.state_key IS UNIQUE",
            "CREATE INDEX recomm_content_type IF NOT EXISTS FOR (c:Content) ON (c.content_type)",
            "CREATE INDEX recomm_content_status IF NOT EXISTS FOR (c:Content) ON (c.status)",
            "CREATE INDEX recomm_content_visibility IF NOT EXISTS FOR (c:Content) ON (c.visibility)",
            "CREATE INDEX recomm_content_published_at IF NOT EXISTS FOR (c:Content) ON (c.published_at)",
        ]
        for statement in statements:
            await self._write(statement)

    async def upsert_users(self, user_ids: list[uuid.UUID]) -> None:
        rows = [{"user_id": str(user_id)} for user_id in user_ids]
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (:User {user_id: row.user_id})
            """,
        )

    async def upsert_subscriptions(self, rows: list[tuple[uuid.UUID, uuid.UUID]]) -> None:
        payload = [
            {
                "subscriber_id": str(subscriber_id),
                "subscribed_id": str(subscribed_id),
            }
            for subscriber_id, subscribed_id in rows
        ]
        await self._run_batched(
            payload,
            """
            UNWIND $rows AS row
            MERGE (subscriber:User {user_id: row.subscriber_id})
            MERGE (subscribed:User {user_id: row.subscribed_id})
            MERGE (subscriber)-[:FOLLOWS]->(subscribed)
            """,
        )

    async def upsert_content_nodes(self, rows: list[dict[str, Any]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (c:Content {content_id: row.content_id})
            SET
                c.author_id = row.author_id,
                c.content_type = row.content_type,
                c.status = row.status,
                c.visibility = row.visibility,
                c.created_at = CASE WHEN row.created_at IS NULL THEN NULL ELSE datetime(row.created_at) END,
                c.published_at = CASE WHEN row.published_at IS NULL THEN NULL ELSE datetime(row.published_at) END,
                c.likes_count = row.likes_count,
                c.dislikes_count = row.dislikes_count,
                c.comments_count = row.comments_count,
                c.views_count = row.views_count,
                c.quality_score = row.quality_score,
                c.updated_at = datetime()
            """,
        )

    async def upsert_authored_edges(self, rows: list[dict[str, str]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (u:User {user_id: row.user_id})
            MERGE (c:Content {content_id: row.content_id})
            MERGE (u)-[:AUTHORED]->(c)
            """,
        )

    async def replace_content_tags(self, *, content_ids: list[uuid.UUID], tag_rows: list[dict[str, str]]) -> None:
        content_rows = [{"content_id": str(content_id)} for content_id in content_ids]
        if content_rows:
            await self._run_batched(
                content_rows,
                """
                UNWIND $rows AS row
                MATCH (c:Content {content_id: row.content_id})-[rel:HAS_TAG]->(:Tag)
                DELETE rel
                """,
            )

        await self._run_batched(
            tag_rows,
            """
            UNWIND $rows AS row
            MERGE (c:Content {content_id: row.content_id})
            MERGE (t:Tag {tag_id: row.tag_id})
            SET t.slug = row.tag_slug
            MERGE (c)-[:HAS_TAG]->(t)
            """,
        )

    async def clear_reactions(self) -> None:
        await self._write("MATCH (:User)-[rel:LIKED|DISLIKED]->(:Content) DELETE rel")

    async def set_liked_edges(self, rows: list[dict[str, Any]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (u:User {user_id: row.user_id})
            MERGE (c:Content {content_id: row.content_id})
            WITH u, c, row
            OPTIONAL MATCH (u)-[op:DISLIKED]->(c)
            DELETE op
            WITH u, c, row
            MERGE (u)-[rel:LIKED]->(c)
            SET rel.updated_at = CASE WHEN row.created_at IS NULL THEN datetime() ELSE datetime(row.created_at) END
            """,
        )

    async def set_disliked_edges(self, rows: list[dict[str, Any]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (u:User {user_id: row.user_id})
            MERGE (c:Content {content_id: row.content_id})
            WITH u, c, row
            OPTIONAL MATCH (u)-[op:LIKED]->(c)
            DELETE op
            WITH u, c, row
            MERGE (u)-[rel:DISLIKED]->(c)
            SET rel.updated_at = CASE WHEN row.created_at IS NULL THEN datetime() ELSE datetime(row.created_at) END
            """,
        )

    async def remove_liked_edges(self, rows: list[dict[str, str]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MATCH (u:User {user_id: row.user_id})-[rel:LIKED]->(c:Content {content_id: row.content_id})
            DELETE rel
            """,
        )

    async def remove_disliked_edges(self, rows: list[dict[str, str]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MATCH (u:User {user_id: row.user_id})-[rel:DISLIKED]->(c:Content {content_id: row.content_id})
            DELETE rel
            """,
        )

    async def clear_viewed_edges(self) -> None:
        await self._write("MATCH (:User)-[rel:VIEWED]->(:Content) DELETE rel")

    async def set_viewed_edges(self, rows: list[dict[str, Any]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (u:User {user_id: row.user_id})
            MERGE (c:Content {content_id: row.content_id})
            MERGE (u)-[rel:VIEWED]->(c)
            SET
                rel.views_count = row.views_count,
                rel.progress_percent = coalesce(row.progress_percent, 0),
                rel.last_seen_at = CASE WHEN row.last_seen_at IS NULL THEN datetime() ELSE datetime(row.last_seen_at) END,
                rel.updated_at = datetime()
            """,
        )

    async def increment_viewed_edges(self, rows: list[dict[str, Any]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (u:User {user_id: row.user_id})
            MERGE (c:Content {content_id: row.content_id})
            MERGE (u)-[rel:VIEWED]->(c)
            ON CREATE SET rel.views_count = 0
            SET
                rel.views_count = coalesce(rel.views_count, 0) + coalesce(row.views_count, 1),
                rel.progress_percent = CASE
                    WHEN row.progress_percent IS NULL THEN coalesce(rel.progress_percent, 0)
                    ELSE CASE
                        WHEN row.progress_percent > coalesce(rel.progress_percent, 0)
                            THEN row.progress_percent
                        ELSE coalesce(rel.progress_percent, 0)
                    END
                END,
                rel.last_seen_at = CASE WHEN row.last_seen_at IS NULL THEN datetime() ELSE datetime(row.last_seen_at) END,
                rel.updated_at = datetime()
            """,
        )

    async def clear_commented_edges(self) -> None:
        await self._write("MATCH (:User)-[rel:COMMENTED]->(:Content) DELETE rel")

    async def set_commented_edges(self, rows: list[dict[str, Any]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (u:User {user_id: row.user_id})
            MERGE (c:Content {content_id: row.content_id})
            MERGE (u)-[rel:COMMENTED]->(c)
            SET
                rel.comments_count = row.comments_count,
                rel.last_commented_at = CASE WHEN row.last_commented_at IS NULL THEN datetime() ELSE datetime(row.last_commented_at) END,
                rel.updated_at = datetime()
            """,
        )

    async def increment_commented_edges(self, rows: list[dict[str, Any]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MERGE (u:User {user_id: row.user_id})
            MERGE (c:Content {content_id: row.content_id})
            MERGE (u)-[rel:COMMENTED]->(c)
            ON CREATE SET rel.comments_count = 0
            SET
                rel.comments_count = coalesce(rel.comments_count, 0) + coalesce(row.comments_count, 1),
                rel.last_commented_at = CASE WHEN row.last_commented_at IS NULL THEN datetime() ELSE datetime(row.last_commented_at) END,
                rel.updated_at = datetime()
            """,
        )

    async def remove_follow_edges(self, rows: list[dict[str, str]]) -> None:
        await self._run_batched(
            rows,
            """
            UNWIND $rows AS row
            MATCH (u:User {user_id: row.user_id})-[rel:FOLLOWS]->(target:User {user_id: row.target_user_id})
            DELETE rel
            """,
        )

    async def recompute_interested_in(self, user_ids: list[uuid.UUID] | None = None) -> None:
        payload = [str(user_id) for user_id in (user_ids or [])]
        await self._write(
            """
            MATCH (u:User)
            WHERE size($user_ids) = 0 OR u.user_id IN $user_ids
            OPTIONAL MATCH (u)-[old:INTERESTED_IN]->(:Tag)
            DELETE old
            WITH DISTINCT u
            CALL (u) {
                MATCH (u)-[:LIKED]->(:Content)-[:HAS_TAG]->(tag:Tag)
                RETURN tag, 4.0 AS weight
                UNION ALL
                MATCH (u)-[:DISLIKED]->(:Content)-[:HAS_TAG]->(tag:Tag)
                RETURN tag, -4.0 AS weight
                UNION ALL
                MATCH (u)-[viewed:VIEWED]->(:Content)-[:HAS_TAG]->(tag:Tag)
                RETURN tag, toFloat(coalesce(viewed.views_count, 1)) AS weight
                UNION ALL
                MATCH (u)-[commented:COMMENTED]->(:Content)-[:HAS_TAG]->(tag:Tag)
                RETURN tag, toFloat(coalesce(commented.comments_count, 1)) * 3.0 AS weight
            }
            WITH u, tag, sum(weight) AS score
            WHERE tag IS NOT NULL AND score > 0
            MERGE (u)-[rel:INTERESTED_IN]->(tag)
            SET rel.weight = score, rel.updated_at = datetime()
            """,
            {"user_ids": payload},
        )

    async def recompute_affinity_to_author(self, user_ids: list[uuid.UUID] | None = None) -> None:
        payload = [str(user_id) for user_id in (user_ids or [])]
        await self._write(
            """
            MATCH (u:User)
            WHERE size($user_ids) = 0 OR u.user_id IN $user_ids
            OPTIONAL MATCH (u)-[old:AFFINITY_TO_AUTHOR]->(:User)
            DELETE old
            WITH DISTINCT u
            CALL (u) {
                MATCH (u)-[:LIKED]->(:Content)<-[:AUTHORED]-(author:User)
                WHERE author.user_id <> u.user_id
                RETURN author, 5.0 AS weight
                UNION ALL
                MATCH (u)-[:DISLIKED]->(:Content)<-[:AUTHORED]-(author:User)
                WHERE author.user_id <> u.user_id
                RETURN author, -6.0 AS weight
                UNION ALL
                MATCH (u)-[viewed:VIEWED]->(:Content)<-[:AUTHORED]-(author:User)
                WHERE author.user_id <> u.user_id
                RETURN author, toFloat(coalesce(viewed.views_count, 1)) AS weight
                UNION ALL
                MATCH (u)-[commented:COMMENTED]->(:Content)<-[:AUTHORED]-(author:User)
                WHERE author.user_id <> u.user_id
                RETURN author, toFloat(coalesce(commented.comments_count, 1)) * 4.0 AS weight
                UNION ALL
                MATCH (u)-[:FOLLOWS]->(author:User)
                WHERE author.user_id <> u.user_id
                RETURN author, 6.0 AS weight
            }
            WITH u, author, sum(weight) AS score
            WHERE author IS NOT NULL AND score > 0
            MERGE (u)-[rel:AFFINITY_TO_AUTHOR]->(author)
            SET rel.weight = score, rel.updated_at = datetime()
            """,
            {"user_ids": payload},
        )

    async def recompute_similar_to(
        self,
        content_ids: list[uuid.UUID] | None = None,
        *,
        per_content_limit: int = 100,
    ) -> None:
        payload = [str(content_id) for content_id in (content_ids or [])]
        await self._write(
            """
            MATCH (c1:Content)
            WHERE size($content_ids) = 0 OR c1.content_id IN $content_ids
            OPTIONAL MATCH (c1)-[old:SIMILAR_TO]->(:Content)
            DELETE old
            WITH DISTINCT c1
            MATCH (c2:Content)
            WHERE c2.content_id <> c1.content_id
            WITH c1, c2
            OPTIONAL MATCH (c1)-[:HAS_TAG]->(tag:Tag)<-[:HAS_TAG]-(c2)
            WITH c1, c2, count(tag) AS shared_tags
            OPTIONAL MATCH (c1)<-[:LIKED]-(:User)-[:LIKED]->(c2)
            WITH c1, c2, shared_tags, count(*) AS co_liked
            OPTIONAL MATCH (c1)<-[:VIEWED]-(:User)-[:VIEWED]->(c2)
            WITH c1, c2, shared_tags, co_liked, count(*) AS co_viewed
            OPTIONAL MATCH (c1)<-[:COMMENTED]-(:User)-[:COMMENTED]->(c2)
            WITH
                c1,
                c2,
                shared_tags,
                co_liked,
                co_viewed,
                count(*) AS co_commented,
                CASE WHEN c1.author_id = c2.author_id THEN 3.0 ELSE 0.0 END AS same_author_boost,
                coalesce(c2.quality_score, 0.0) AS quality_score
            WITH
                c1,
                c2,
                shared_tags,
                co_liked,
                co_viewed,
                co_commented,
                same_author_boost,
                quality_score,
                (
                    (toFloat(shared_tags) * 2.5)
                    + (toFloat(co_liked) * 3.0)
                    + (toFloat(co_viewed) * 1.0)
                    + (toFloat(co_commented) * 2.0)
                    + same_author_boost
                    + (quality_score * 0.15)
                ) AS score
            WHERE score > 0
            ORDER BY score DESC
            WITH c1, collect({
                other: c2,
                score: score,
                shared_tags: shared_tags,
                co_liked: co_liked,
                co_viewed: co_viewed,
                co_commented: co_commented,
                same_author_boost: same_author_boost
            })[..$per_content_limit] AS recs
            UNWIND recs AS rec
            WITH c1, rec, rec.other AS other
            MERGE (c1)-[rel:SIMILAR_TO]->(other)
            SET
                rel.score = rec.score,
                rel.shared_tags = rec.shared_tags,
                rel.co_liked = rec.co_liked,
                rel.co_viewed = rec.co_viewed,
                rel.co_commented = rec.co_commented,
                rel.reason = CASE
                    WHEN rec.same_author_boost > 0
                        AND rec.same_author_boost >= (toFloat(rec.shared_tags) * 2.5)
                        AND rec.same_author_boost >= ((toFloat(rec.co_liked) * 3.0) + (toFloat(rec.co_viewed) * 1.0) + (toFloat(rec.co_commented) * 2.0))
                        THEN 'same_author'
                    WHEN rec.shared_tags > 0
                        AND (toFloat(rec.shared_tags) * 2.5) >= ((toFloat(rec.co_liked) * 3.0) + (toFloat(rec.co_viewed) * 1.0) + (toFloat(rec.co_commented) * 2.0))
                        THEN 'shared_tags'
                    WHEN (rec.co_liked + rec.co_viewed + rec.co_commented) > 0
                        THEN 'shared_audience'
                    ELSE 'quality'
                END,
                rel.updated_at = datetime()
            """,
            {
                "content_ids": payload,
                "per_content_limit": per_content_limit,
            },
        )

    async def get_sync_state(
        self,
        *,
        state_key: RecommendationSyncStateKey = RecommendationSyncStateKey.MAIN,
    ) -> RecommendationGraphSyncState | None:
        rows = await self._read(
            """
            MATCH (s:RecommendationSyncState {state_key: $state_key})
            RETURN s.last_event_at AS last_event_at, s.last_event_id AS last_event_id, s.last_full_rebuild_at AS last_full_rebuild_at
            """,
            {"state_key": state_key.value},
        )
        row = rows[0] if rows else None
        if row is None:
            return None

        last_event_id = row.get("last_event_id")
        return RecommendationGraphSyncState(
            last_event_at=self._normalize_neo4j_datetime(row.get("last_event_at")),
            last_event_id=uuid.UUID(last_event_id) if isinstance(last_event_id, str) else None,
            last_full_rebuild_at=self._normalize_neo4j_datetime(row.get("last_full_rebuild_at")),
        )

    async def upsert_sync_state(
        self,
        *,
        last_event_at: datetime.datetime | None,
        last_event_id: uuid.UUID | None,
        last_full_rebuild_at: datetime.datetime | None,
        state_key: RecommendationSyncStateKey = RecommendationSyncStateKey.MAIN,
    ) -> None:
        await self._write(
            """
            MERGE (s:RecommendationSyncState {state_key: $state_key})
            SET
                s.last_event_at = CASE WHEN $last_event_at IS NULL THEN s.last_event_at ELSE datetime($last_event_at) END,
                s.last_event_id = CASE WHEN $last_event_id IS NULL THEN s.last_event_id ELSE $last_event_id END,
                s.last_full_rebuild_at = CASE WHEN $last_full_rebuild_at IS NULL THEN s.last_full_rebuild_at ELSE datetime($last_full_rebuild_at) END,
                s.updated_at = datetime()
            """,
            {
                "state_key": state_key.value,
                "last_event_at": self._datetime_to_iso(last_event_at),
                "last_event_id": str(last_event_id) if last_event_id is not None else None,
                "last_full_rebuild_at": self._datetime_to_iso(last_full_rebuild_at),
            },
        )

    async def get_similar_content(
        self,
        *,
        content_id: uuid.UUID,
        limit: int,
        content_type: str | None,
    ) -> list[SimilarContentGraphResult]:
        rows = await self._read(
            """
            MATCH (:Content {content_id: $content_id})-[rel:SIMILAR_TO]->(candidate:Content)
            WHERE ($content_type IS NULL OR candidate.content_type = $content_type)
            RETURN candidate.content_id AS content_id, rel.score AS score, coalesce(rel.reason, 'quality') AS reason
            ORDER BY rel.score DESC
            LIMIT $limit
            """,
            {
                "content_id": str(content_id),
                "limit": limit,
                "content_type": content_type,
            },
        )

        result: list[SimilarContentGraphResult] = []
        for row in rows:
            candidate_content_id = row.get("content_id")
            if not isinstance(candidate_content_id, str):
                continue
            result.append(
                SimilarContentGraphResult(
                    content_id=uuid.UUID(candidate_content_id),
                    score=float(row.get("score") or 0.0),
                    reason=str(row.get("reason") or "quality"),
                )
            )
        return result

    async def get_recommendation_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        content_type: str | None,
        sort: str,
        offset: int,
        limit: int,
    ) -> list[RecommendationFeedGraphResult]:
        rows = await self._read(
            """
            OPTIONAL MATCH (viewer:User {user_id: $viewer_id})
            MATCH (candidate:Content)
            WHERE candidate.status = 'published'
                AND candidate.visibility = 'public'
                AND ($content_type IS NULL OR candidate.content_type = $content_type)
                AND (
                    viewer IS NULL
                    OR candidate.author_id IS NULL
                    OR candidate.author_id <> viewer.user_id
                )
                AND (
                    viewer IS NULL
                    OR NOT EXISTS {
                        MATCH (viewer)-[:DISLIKED]->(candidate)
                    }
                )
                AND (
                    viewer IS NULL
                    OR NOT EXISTS {
                        MATCH (viewer)-[seen:VIEWED]->(candidate)
                        WHERE coalesce(seen.progress_percent, 0) >= 90
                    }
                )
            OPTIONAL MATCH (viewer)-[interest:INTERESTED_IN]->(:Tag)<-[:HAS_TAG]-(candidate)
            WITH viewer, candidate, coalesce(sum(interest.weight), 0.0) AS tag_affinity
            OPTIONAL MATCH (viewer)-[author_affinity:AFFINITY_TO_AUTHOR]->(:User)-[:AUTHORED]->(candidate)
            WITH
                viewer,
                candidate,
                tag_affinity,
                coalesce(sum(author_affinity.weight), 0.0) AS author_affinity
            CALL {
                WITH viewer, candidate
                WITH viewer, candidate WHERE viewer IS NOT NULL
                MATCH (viewer)-[:LIKED|VIEWED|COMMENTED]->(seed:Content)<-[:LIKED|VIEWED|COMMENTED]-(peer:User)
                WHERE peer.user_id <> viewer.user_id
                WITH candidate, peer, count(DISTINCT seed) AS overlap
                WHERE overlap > 0
                MATCH (peer)-[peer_rel:LIKED|VIEWED|COMMENTED]->(candidate)
                RETURN coalesce(sum(
                    CASE type(peer_rel)
                        WHEN 'LIKED' THEN toFloat(overlap) * $collaborative_like_weight
                        WHEN 'VIEWED' THEN toFloat(overlap) * $collaborative_view_weight
                        WHEN 'COMMENTED' THEN toFloat(overlap) * $collaborative_comment_weight
                        ELSE 0.0
                    END
                ), 0.0) AS collaborative_score
                UNION
                WITH candidate
                RETURN 0.0 AS collaborative_score
            }
            WITH
                candidate,
                tag_affinity,
                author_affinity,
                max(collaborative_score) AS collaborative_score
            WITH
                candidate,
                tag_affinity,
                author_affinity,
                collaborative_score,
                coalesce(candidate.quality_score, 0.0) AS content_quality_score,
                duration.inDays(coalesce(candidate.published_at, candidate.created_at), datetime()).days AS age_days
            WITH
                candidate,
                tag_affinity,
                author_affinity,
                collaborative_score,
                content_quality_score,
                (
                    1.0
                    / (1.0 + (toFloat(abs(coalesce(age_days, 0))) / $freshness_decay_days))
                ) AS freshness_score
            WITH
                candidate,
                tag_affinity,
                author_affinity,
                collaborative_score,
                content_quality_score,
                freshness_score,
                (
                    (tag_affinity * $tag_affinity_weight)
                    + (author_affinity * $author_affinity_weight)
                    + (collaborative_score * $collaborative_weight)
                    + (content_quality_score * $content_quality_weight)
                    + (freshness_score * $freshness_weight)
                ) AS score,
                coalesce(candidate.published_at, candidate.created_at) AS published_sort
            WITH candidate, score, published_sort
            ORDER BY
                CASE WHEN $sort = 'relevance' THEN score ELSE 0.0 END DESC,
                CASE WHEN $sort = 'newest' THEN published_sort END DESC,
                CASE WHEN $sort = 'oldest' THEN published_sort END ASC,
                CASE WHEN $sort = 'relevance' THEN published_sort END DESC
            SKIP $offset
            LIMIT $limit
            RETURN
                candidate.content_id AS content_id,
                score AS score,
                'personalized_graph_feed' AS reason
            """,
            {
                "viewer_id": str(viewer_id) if viewer_id is not None else None,
                "content_type": content_type,
                "sort": sort,
                "offset": offset,
                "limit": limit,
                "tag_affinity_weight": TAG_AFFINITY_WEIGHT,
                "author_affinity_weight": AUTHOR_AFFINITY_WEIGHT,
                "collaborative_weight": COLLABORATIVE_WEIGHT,
                "content_quality_weight": CONTENT_QUALITY_WEIGHT,
                "freshness_weight": FRESHNESS_WEIGHT,
                "freshness_decay_days": FRESHNESS_DECAY_DAYS,
                "collaborative_like_weight": COLLABORATIVE_LIKE_WEIGHT,
                "collaborative_view_weight": COLLABORATIVE_VIEW_WEIGHT,
                "collaborative_comment_weight": COLLABORATIVE_COMMENT_WEIGHT,
            },
        )

        result: list[RecommendationFeedGraphResult] = []
        for row in rows:
            candidate_content_id = row.get("content_id")
            if not isinstance(candidate_content_id, str):
                continue
            result.append(
                RecommendationFeedGraphResult(
                    content_id=uuid.UUID(candidate_content_id),
                    score=float(row.get("score") or 0.0),
                    reason=str(row.get("reason") or "personalized_graph_feed"),
                )
            )
        return result

    async def _run_batched(self, rows: list[dict[str, Any]], query: str, *, batch_size: int = 1000) -> None:
        if not rows:
            return
        for offset in range(0, len(rows), batch_size):
            chunk = rows[offset: offset + batch_size]
            await self._write(query, {"rows": chunk})

    async def _write(self, query: str, parameters: dict[str, Any] | None = None) -> None:
        async with self._driver.session(database=self._database) as session:
            await session.execute_write(self._run_query, query, parameters or {})

    async def _read(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        async with self._driver.session(database=self._database) as session:
            return await session.execute_read(self._fetch_query, query, parameters or {})

    @staticmethod
    async def _run_query(tx, query: str, parameters: dict[str, Any]):  # type: ignore[no-untyped-def]
        result = await tx.run(query, parameters)
        await result.consume()

    @staticmethod
    async def _fetch_query(tx, query: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
        result = await tx.run(query, parameters)
        records = await result.data()
        return [dict(record) for record in records]

    @staticmethod
    def _datetime_to_iso(value: datetime.datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc).isoformat()

    @staticmethod
    def _normalize_neo4j_datetime(value) -> datetime.datetime | None:  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=datetime.timezone.utc)
            return value
        to_native = getattr(value, "to_native", None)
        if callable(to_native):
            native = to_native()
            if isinstance(native, datetime.datetime):
                if native.tzinfo is None:
                    return native.replace(tzinfo=datetime.timezone.utc)
                return native
        return None
