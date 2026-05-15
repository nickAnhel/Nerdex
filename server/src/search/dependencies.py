from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage
from src.common.database import get_async_session
from src.content.projectors import build_default_content_projector_registry
from src.search.repository import SearchRepository
from src.search.service import SearchService


async def get_search_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> SearchService:
    return SearchService(
        repository=SearchRepository(async_session),
        projector_registry=build_default_content_projector_registry(),
        asset_storage=get_asset_storage(),
    )
