from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage, get_task_dispatcher
from src.assets.repository import AssetRepository
from src.assets.service import AssetService
from src.common.database import get_async_session
from src.config import settings
from src.moments.repository import MomentRepository
from src.moments.service import MomentService
from src.tags.repository import TagRepository
from src.tags.service import TagService


async def get_moment_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> MomentService:
    return MomentService(
        repository=MomentRepository(async_session),
        tag_service=TagService(repository=TagRepository(async_session)),
        asset_repository=AssetRepository(async_session),
        asset_service=AssetService(
            repository=AssetRepository(async_session),
            storage=get_asset_storage(),
            settings=settings.assets,
            task_dispatcher=get_task_dispatcher(),
        ),
        asset_storage=get_asset_storage(),
    )
