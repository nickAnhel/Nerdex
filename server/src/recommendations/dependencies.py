from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage
from src.common.database import get_async_session
from src.content.projectors import build_default_content_projector_registry
from src.recommendations.graph_repository import RecommendationGraphRepository, create_neo4j_driver
from src.recommendations.postgres_repository import RecommendationPostgresRepository
from src.recommendations.service import RecommendationService
from src.recommendations.sync_service import RecommendationGraphSyncService
from src.config import settings


async def get_recommendation_graph_repository() -> AsyncGenerator[RecommendationGraphRepository, None]:
    driver = create_neo4j_driver()
    repository = RecommendationGraphRepository(driver=driver, database=settings.neo4j.database)
    try:
        yield repository
    finally:
        await repository.close()


async def get_recommendation_service(
    async_session: AsyncSession = Depends(get_async_session),
    graph_repository: RecommendationGraphRepository = Depends(get_recommendation_graph_repository),
) -> RecommendationService:
    return RecommendationService(
        graph_repository=graph_repository,
        postgres_repository=RecommendationPostgresRepository(async_session),
        projector_registry=build_default_content_projector_registry(),
        asset_storage=get_asset_storage(),
    )


async def get_recommendation_graph_sync_service(
    async_session: AsyncSession = Depends(get_async_session),
    graph_repository: RecommendationGraphRepository = Depends(get_recommendation_graph_repository),
) -> RecommendationGraphSyncService:
    return RecommendationGraphSyncService(
        postgres_repository=RecommendationPostgresRepository(async_session),
        graph_repository=graph_repository,
    )
