from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.posts.repository import PostRepository
from src.posts.service import PostService


async def get_post_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> PostService:
    return PostService(repository=PostRepository(async_session))
