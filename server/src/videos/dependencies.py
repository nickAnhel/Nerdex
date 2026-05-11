from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage, get_task_dispatcher
from src.assets.repository import AssetRepository
from src.assets.service import AssetService
from src.common.database import get_async_session
from src.config import settings
from src.tags.repository import TagRepository
from src.tags.service import TagService
from src.videos.repository import VideoRepository
from src.videos.service import VideoService


async def get_video_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> VideoService:
    return VideoService(
        repository=VideoRepository(async_session),
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
