from __future__ import annotations

import logging
import time
import uuid

from src.content.enums import ContentTypeEnum
from src.content.projectors import ContentProjectorRegistry
from src.content.schemas import ContentListItemGet
from src.config import settings
from src.observability.context import get_request_id
from src.observability.metrics import (
    observe_recommendations_authors,
    observe_recommendations_feed,
    observe_recommendations_similar,
)
from src.recommendations.graph_repository import (
    RecommendationAuthorGraphResult,
    RecommendationFeedGraphResult,
    RecommendationGraphRepository,
)
from src.recommendations.postgres_repository import RecommendationPostgresRepository
from src.recommendations.schemas import (
    RecommendedAuthorItemGet,
    RecommendationFeedContentTypeEnum,
    RecommendationFeedSortEnum,
    SimilarContentItemGet,
    SimilarContentListGet,
)
from src.users.presentation import build_user_get


logger = logging.getLogger(__name__)


class RecommendationService:
    def __init__(
        self,
        *,
        graph_repository: RecommendationGraphRepository,
        postgres_repository: RecommendationPostgresRepository,
        projector_registry: ContentProjectorRegistry,
        asset_storage,
    ) -> None:
        self._graph_repository = graph_repository
        self._postgres_repository = postgres_repository
        self._projector_registry = projector_registry
        self._asset_storage = asset_storage

    async def get_similar_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        limit: int,
        content_type: ContentTypeEnum | None,
    ) -> SimilarContentListGet:
        started_at = time.perf_counter()
        request_id = get_request_id()
        graph_limit = max(limit * 4, limit)
        neo4j_ms = 0.0
        postgres_hydration_ms = 0.0
        projection_ms = 0.0
        graph_started_at = time.perf_counter()

        try:
            graph_rows = await self._graph_repository.get_similar_content(
                content_id=content_id,
                limit=graph_limit,
                content_type=content_type.value if content_type is not None else None,
            )
            neo4j_ms = self._to_milliseconds(time.perf_counter() - graph_started_at)
        except Exception:
            neo4j_ms = self._to_milliseconds(time.perf_counter() - graph_started_at)
            logger.exception("Neo4j similar-content query failed")
            total_ms = self._to_milliseconds(time.perf_counter() - started_at)
            observe_recommendations_similar(total_seconds=total_ms / 1000)
            self._log_timing_event(
                level=logging.ERROR,
                message="recommendations similar completed",
                extra={
                    "event": "recommendations.similar",
                    "request_id": request_id,
                    "content_id": str(content_id),
                    "viewer_id": str(viewer_id) if viewer_id is not None else None,
                    "neo4j_ms": neo4j_ms,
                    "postgres_hydration_ms": postgres_hydration_ms,
                    "projection_ms": projection_ms,
                    "total_ms": total_ms,
                    "items_count": 0,
                    "error": True,
                },
            )
            return SimilarContentListGet(items=[], limit=limit)

        if not graph_rows:
            total_ms = self._to_milliseconds(time.perf_counter() - started_at)
            observe_recommendations_similar(total_seconds=total_ms / 1000)
            self._log_timing_event(
                level=logging.INFO,
                message="recommendations similar completed",
                extra={
                    "event": "recommendations.similar",
                    "request_id": request_id,
                    "content_id": str(content_id),
                    "viewer_id": str(viewer_id) if viewer_id is not None else None,
                    "neo4j_ms": neo4j_ms,
                    "postgres_hydration_ms": postgres_hydration_ms,
                    "projection_ms": projection_ms,
                    "total_ms": total_ms,
                    "items_count": 0,
                    "error": False,
                },
            )
            return SimilarContentListGet(items=[], limit=limit)

        hydration_started_at = time.perf_counter()
        hydrated = await self._postgres_repository.get_visible_content_by_ids(
            content_ids=[row.content_id for row in graph_rows],
            viewer_id=viewer_id,
        )
        postgres_hydration_ms = self._to_milliseconds(time.perf_counter() - hydration_started_at)

        projection_started_at = time.perf_counter()
        items: list[SimilarContentItemGet] = []
        for row in graph_rows:
            content = hydrated.get(row.content_id)
            if content is None:
                continue
            if content_type is not None and content.content_type != content_type:
                continue
            projector = self._projector_registry.get(content.content_type)
            projected = await projector.project_feed_item(
                content,
                viewer_id=viewer_id,
                storage=self._asset_storage,
            )
            items.append(
                SimilarContentItemGet(
                    content_id=row.content_id,
                    score=row.score,
                    reason=row.reason,
                    content=projected,
                )
            )
            if len(items) >= limit:
                break
        projection_ms = self._to_milliseconds(time.perf_counter() - projection_started_at)

        total_ms = self._to_milliseconds(time.perf_counter() - started_at)
        observe_recommendations_similar(total_seconds=total_ms / 1000)
        self._log_timing_event(
            level=self._slow_level(total_ms),
            message="recommendations similar completed",
            extra={
                "event": "recommendations.similar",
                "request_id": request_id,
                "content_id": str(content_id),
                "viewer_id": str(viewer_id) if viewer_id is not None else None,
                "neo4j_ms": neo4j_ms,
                "postgres_hydration_ms": postgres_hydration_ms,
                "projection_ms": projection_ms,
                "total_ms": total_ms,
                "items_count": len(items),
                "error": False,
            },
        )

        return SimilarContentListGet(items=items, limit=limit)

    async def get_recommendations_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        content_type: RecommendationFeedContentTypeEnum,
        sort: RecommendationFeedSortEnum,
        offset: int,
        limit: int,
    ) -> list[ContentListItemGet]:
        started_at = time.perf_counter()
        request_id = get_request_id()
        target_content_type = self._resolve_content_type(content_type)
        graph_limit = max(limit * 4, limit)

        graph_rows = []
        graph_failed = False
        neo4j_ms = 0.0
        postgres_hydration_ms = 0.0
        fallback_ms = 0.0
        projection_ms = 0.0
        fallback_used = False
        graph_started_at = time.perf_counter()
        try:
            graph_rows = await self._graph_repository.get_recommendation_feed(
                viewer_id=viewer_id,
                content_type=target_content_type.value if target_content_type is not None else None,
                sort=sort.value,
                offset=offset,
                limit=graph_limit,
            )
            neo4j_ms = self._to_milliseconds(time.perf_counter() - graph_started_at)
        except Exception:
            graph_failed = True
            logger.exception("Neo4j recommendations feed query failed")
            neo4j_ms = self._to_milliseconds(time.perf_counter() - graph_started_at)

        hydrated = {}
        if graph_rows:
            hydration_started_at = time.perf_counter()
            hydrated = await self._postgres_repository.get_visible_content_by_ids(
                content_ids=[row.content_id for row in graph_rows],
                viewer_id=viewer_id,
            )
            postgres_hydration_ms = self._to_milliseconds(time.perf_counter() - hydration_started_at)

        projection_started_at = time.perf_counter()
        items = await self._project_recommendation_rows(
            rows=graph_rows,
            hydrated=hydrated,
            viewer_id=viewer_id,
            content_type=target_content_type,
            limit=limit,
        )
        projection_ms += self._to_milliseconds(time.perf_counter() - projection_started_at)
        if len(items) >= limit:
            total_ms = self._to_milliseconds(time.perf_counter() - started_at)
            observe_recommendations_feed(
                total_seconds=total_ms / 1000,
                neo4j_seconds=neo4j_ms / 1000,
                postgres_seconds=postgres_hydration_ms / 1000,
            )
            self._log_timing_event(
                level=self._slow_level(total_ms),
                message="recommendations feed completed",
                extra={
                    "event": "recommendations.feed",
                    "request_id": request_id,
                    "viewer_id": str(viewer_id) if viewer_id is not None else None,
                    "content_type": content_type.value,
                    "sort": sort.value,
                    "offset": offset,
                    "limit": limit,
                    "neo4j_ms": neo4j_ms,
                    "postgres_hydration_ms": postgres_hydration_ms,
                    "fallback_ms": fallback_ms,
                    "projection_ms": projection_ms,
                    "total_ms": total_ms,
                    "items_count": len(items),
                    "fallback_used": fallback_used,
                    "error": graph_failed,
                },
            )
            return items

        fallback_needed = limit - len(items)
        fallback_started_at = time.perf_counter()
        fallback_items = await self._postgres_repository.get_recommendation_fallback_content(
            viewer_id=viewer_id,
            content_type=target_content_type,
            sort=sort.value,
            offset=offset if graph_failed else 0,
            limit=fallback_needed,
            exclude_content_ids=[item.content_id for item in items],
        )
        fallback_ms = self._to_milliseconds(time.perf_counter() - fallback_started_at)
        fallback_used = bool(fallback_items)

        fallback_projection_started_at = time.perf_counter()
        for content in fallback_items:
            items.append(await self._project_content(content=content, viewer_id=viewer_id))
            if len(items) >= limit:
                break
        projection_ms += self._to_milliseconds(time.perf_counter() - fallback_projection_started_at)

        total_ms = self._to_milliseconds(time.perf_counter() - started_at)
        observe_recommendations_feed(
            total_seconds=total_ms / 1000,
            neo4j_seconds=neo4j_ms / 1000,
            postgres_seconds=postgres_hydration_ms / 1000,
        )
        self._log_timing_event(
            level=self._slow_level(total_ms),
            message="recommendations feed completed",
            extra={
                "event": "recommendations.feed",
                "request_id": request_id,
                "viewer_id": str(viewer_id) if viewer_id is not None else None,
                "content_type": content_type.value,
                "sort": sort.value,
                "offset": offset,
                "limit": limit,
                "neo4j_ms": neo4j_ms,
                "postgres_hydration_ms": postgres_hydration_ms,
                "fallback_ms": fallback_ms,
                "projection_ms": projection_ms,
                "total_ms": total_ms,
                "items_count": len(items),
                "fallback_used": fallback_used,
                "error": graph_failed,
            },
        )

        return items

    async def get_recommended_authors(
        self,
        *,
        viewer_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> list[RecommendedAuthorItemGet]:
        started_at = time.perf_counter()
        request_id = get_request_id()
        graph_limit = max(limit * 4, limit)
        neo4j_ms = 0.0
        postgres_ms = 0.0
        graph_started_at = time.perf_counter()

        graph_rows: list[RecommendationAuthorGraphResult] = []
        try:
            graph_rows = await self._graph_repository.get_recommended_authors(
                viewer_id=viewer_id,
                offset=offset,
                limit=graph_limit,
            )
            neo4j_ms = self._to_milliseconds(time.perf_counter() - graph_started_at)
        except Exception:
            neo4j_ms = self._to_milliseconds(time.perf_counter() - graph_started_at)
            logger.exception("Neo4j recommended-authors query failed")
            total_ms = self._to_milliseconds(time.perf_counter() - started_at)
            observe_recommendations_authors(total_seconds=total_ms / 1000)
            self._log_timing_event(
                level=logging.ERROR,
                message="recommendations authors completed",
                extra={
                    "event": "recommendations.authors",
                    "request_id": request_id,
                    "viewer_id": str(viewer_id),
                    "neo4j_ms": neo4j_ms,
                    "postgres_ms": postgres_ms,
                    "total_ms": total_ms,
                    "items_count": 0,
                    "error": True,
                },
            )
            return []

        if not graph_rows:
            total_ms = self._to_milliseconds(time.perf_counter() - started_at)
            observe_recommendations_authors(total_seconds=total_ms / 1000)
            self._log_timing_event(
                level=logging.INFO,
                message="recommendations authors completed",
                extra={
                    "event": "recommendations.authors",
                    "request_id": request_id,
                    "viewer_id": str(viewer_id),
                    "neo4j_ms": neo4j_ms,
                    "postgres_ms": postgres_ms,
                    "total_ms": total_ms,
                    "items_count": 0,
                    "error": False,
                },
            )
            return []

        candidate_user_ids = [row.user_id for row in graph_rows]
        postgres_started_at = time.perf_counter()
        users_by_id = await self._postgres_repository.get_users_by_ids(user_ids=candidate_user_ids)
        visible_author_ids = await self._postgres_repository.get_public_author_ids_by_ids(author_ids=candidate_user_ids)
        subscribed_author_ids = await self._postgres_repository.get_subscribed_user_ids(subscriber_id=viewer_id)
        postgres_ms = self._to_milliseconds(time.perf_counter() - postgres_started_at)

        items: list[RecommendedAuthorItemGet] = []
        for row in graph_rows:
            if row.user_id == viewer_id:
                continue
            if row.user_id in subscribed_author_ids:
                continue
            if row.user_id not in visible_author_ids:
                continue

            author_model = users_by_id.get(row.user_id)
            if author_model is None:
                continue

            author = await build_user_get(
                author_model,
                viewer_id=viewer_id,
                storage=self._asset_storage,
            )
            if bool(author.is_subscribed):
                continue

            items.append(
                RecommendedAuthorItemGet(
                    user_id=row.user_id,
                    score=row.score,
                    reason=row.reason,
                    author=author,
                )
            )
            if len(items) >= limit:
                break

        total_ms = self._to_milliseconds(time.perf_counter() - started_at)
        observe_recommendations_authors(total_seconds=total_ms / 1000)
        self._log_timing_event(
            level=self._slow_level(total_ms),
            message="recommendations authors completed",
            extra={
                "event": "recommendations.authors",
                "request_id": request_id,
                "viewer_id": str(viewer_id),
                "neo4j_ms": neo4j_ms,
                "postgres_ms": postgres_ms,
                "total_ms": total_ms,
                "items_count": len(items),
                "error": False,
            },
        )

        return items

    async def _project_recommendation_rows(
        self,
        *,
        rows: list[RecommendationFeedGraphResult],
        hydrated: dict[uuid.UUID, object],
        viewer_id: uuid.UUID | None,
        content_type: ContentTypeEnum | None,
        limit: int,
    ) -> list[ContentListItemGet]:
        if not rows:
            return []
        items: list[ContentListItemGet] = []
        for row in rows:
            content = hydrated.get(row.content_id)
            if content is None:
                continue
            if content_type is not None and content.content_type != content_type:
                continue
            items.append(await self._project_content(content=content, viewer_id=viewer_id))
            if len(items) >= limit:
                break
        return items

    async def _project_content(self, *, content, viewer_id: uuid.UUID | None) -> ContentListItemGet:
        projector = self._projector_registry.get(content.content_type)
        return await projector.project_feed_item(
            content,
            viewer_id=viewer_id,
            storage=self._asset_storage,
        )

    @staticmethod
    def _resolve_content_type(
        content_type: RecommendationFeedContentTypeEnum,
    ) -> ContentTypeEnum | None:
        if content_type == RecommendationFeedContentTypeEnum.ALL:
            return None
        return ContentTypeEnum(content_type.value)

    @staticmethod
    def _to_milliseconds(duration_seconds: float) -> float:
        return round(duration_seconds * 1000, 3)

    @staticmethod
    def _log_timing_event(*, level: int, message: str, extra: dict) -> None:
        logger.log(level, message, extra=extra)

    @staticmethod
    def _slow_level(total_ms: float) -> int:
        if total_ms > settings.logging.slow_recommendation_threshold_ms:
            return logging.WARNING
        return logging.INFO
