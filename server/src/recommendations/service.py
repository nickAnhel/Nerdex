from __future__ import annotations

import logging
import uuid

from src.content.enums import ContentTypeEnum
from src.content.projectors import ContentProjectorRegistry
from src.recommendations.graph_repository import RecommendationGraphRepository
from src.recommendations.postgres_repository import RecommendationPostgresRepository
from src.recommendations.schemas import SimilarContentItemGet, SimilarContentListGet


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
