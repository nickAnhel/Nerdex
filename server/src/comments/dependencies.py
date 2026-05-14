from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.repository import ActivityRepository
from src.activity.service import ActivityService
from src.assets.dependencies import get_asset_storage
from src.comments.repository import CommentRepository
from src.comments.service import CommentService
from src.common.database import get_async_session
from src.content.projectors import build_default_content_projector_registry
from src.users.repository import UserRepository


async def get_comment_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> CommentService:
    return CommentService(
        repository=CommentRepository(async_session),
        user_repository=UserRepository(async_session),
        activity_service=ActivityService(
            repository=ActivityRepository(async_session),
            asset_storage=get_asset_storage(),
            projector_registry=build_default_content_projector_registry(),
        ),
    )
