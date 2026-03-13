from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.repository import AssetRepository
from src.assets.service import AssetService, TaskDispatcher
from src.assets.storage import AssetStorage
from src.common.database import get_async_session
from src.config import settings


def get_asset_storage() -> AssetStorage:
    return AssetStorage(settings.storage)


def get_task_dispatcher() -> TaskDispatcher:
    from src.assets.tasks import enqueue_image_processing, enqueue_video_processing

    return TaskDispatcher(
        enqueue_image_processing=enqueue_image_processing,
        enqueue_video_processing=enqueue_video_processing,
    )


async def get_asset_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> AssetService:
    return AssetService(
        repository=AssetRepository(async_session),
        storage=get_asset_storage(),
        settings=settings.assets,
        task_dispatcher=get_task_dispatcher(),
    )
