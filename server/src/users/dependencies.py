from src.assets.dependencies import get_asset_service, get_asset_storage
from src.assets.service import AssetService
from src.assets.storage import AssetStorage
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.repository import ActivityRepository
from src.activity.service import ActivityService
from src.content.projectors import build_default_content_projector_registry
from src.common.database import get_async_session
from src.users.repository import UserRepository
from src.users.service import UserService


async def get_user_service(
    async_session: AsyncSession = Depends(get_async_session),
    asset_service: AssetService = Depends(get_asset_service),
    avatar_storage: AssetStorage = Depends(get_asset_storage),
) -> UserService:
    return UserService(
        repository=UserRepository(async_session),
        asset_service=asset_service,
        avatar_storage=avatar_storage,
        activity_service=ActivityService(
            repository=ActivityRepository(async_session),
            asset_storage=avatar_storage,
            projector_registry=build_default_content_projector_registry(),
        ),
    )
