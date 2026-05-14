from src.assets.dependencies import get_asset_storage, get_task_dispatcher
from src.assets.repository import AssetRepository
from src.assets.service import AssetService
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.repository import ActivityRepository
from src.activity.service import ActivityService
from src.common.database import get_async_session
from src.config import settings
from src.content.projectors import build_default_content_projector_registry
from src.posts.repository import PostRepository
from src.posts.service import PostService
from src.tags.repository import TagRepository
from src.tags.service import TagService


async def get_post_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> PostService:
    return PostService(
        repository=PostRepository(async_session),
        tag_service=TagService(repository=TagRepository(async_session)),
        asset_repository=AssetRepository(async_session),
        asset_service=AssetService(
            repository=AssetRepository(async_session),
            storage=get_asset_storage(),
            settings=settings.assets,
            task_dispatcher=get_task_dispatcher(),
        ),
        asset_storage=get_asset_storage(),
        activity_service=ActivityService(
            repository=ActivityRepository(async_session),
            asset_storage=get_asset_storage(),
            projector_registry=build_default_content_projector_registry(),
        ),
    )
