from __future__ import annotations

import logging
import uuid

from src.content.enums import ContentTypeEnum
from src.content.projectors import ContentProjectorRegistry
from src.content.schemas import ContentListItemGet
from src.recommendations.graph_repository import (
    RecommendationFeedGraphResult,
    RecommendationGraphRepository,
)
from src.recommendations.postgres_repository import RecommendationPostgresRepository
from src.recommendations.schemas import (
    RecommendationFeedContentTypeEnum,
    RecommendationFeedSortEnum,
    SimilarContentItemGet,
    SimilarContentListGet,
)


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
        graph_limit = max(limit * 4, limit)
        try:
            graph_rows = await self._graph_repository.get_similar_content(
                content_id=content_id,
                limit=graph_limit,
                content_type=content_type.value if content_type is not None else None,
            )
        except Exception:
            logger.exception("Neo4j similar-content query failed")
            return SimilarContentListGet(items=[], limit=limit)

        if not graph_rows:
            return SimilarContentListGet(items=[], limit=limit)

        hydrated = await self._postgres_repository.get_visible_content_by_ids(
            content_ids=[row.content_id for row in graph_rows],
            viewer_id=viewer_id,
        )

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
        target_content_type = self._resolve_content_type(content_type)
        graph_limit = max(limit * 4, limit)

        graph_rows = []
        graph_failed = False
        try:
            graph_rows = await self._graph_repository.get_recommendation_feed(
                viewer_id=viewer_id,
                content_type=target_content_type.value if target_content_type is not None else None,
                sort=sort.value,
                offset=offset,
                limit=graph_limit,
            )
        except Exception:
            graph_failed = True
            logger.exception("Neo4j recommendations feed query failed")

        items = await self._hydrate_recommendation_rows(
            rows=graph_rows,
            viewer_id=viewer_id,
            content_type=target_content_type,
            limit=limit,
        )
        if len(items) >= limit:
            return items

        fallback_needed = limit - len(items)
        fallback_items = await self._postgres_repository.get_recommendation_fallback_content(
            viewer_id=viewer_id,
            content_type=target_content_type,
            sort=sort.value,
            offset=offset if graph_failed else 0,
            limit=fallback_needed,
            exclude_content_ids=[item.content_id for item in items],
        )
        for content in fallback_items:
            items.append(await self._project_content(content=content, viewer_id=viewer_id))
            if len(items) >= limit:
                break

        return items

    async def _hydrate_recommendation_rows(
        self,
        *,
        rows: list[RecommendationFeedGraphResult],
        viewer_id: uuid.UUID | None,
        content_type: ContentTypeEnum | None,
        limit: int,
    ) -> list[ContentListItemGet]:
        if not rows:
            return []

        hydrated = await self._postgres_repository.get_visible_content_by_ids(
            content_ids=[row.content_id for row in rows],
            viewer_id=viewer_id,
        )
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
