from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import get_async_session
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
    )
