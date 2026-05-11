from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage
from src.common.database import get_async_session
from src.content.projectors import build_default_content_projector_registry
from src.content.repository import ContentRepository
from src.content.service import ContentService


async def get_content_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> ContentService:
    return ContentService(
        repository=ContentRepository(async_session),
        asset_storage=get_asset_storage(),
        projector_registry=build_default_content_projector_registry(),
    )
