from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.database import get_async_session
from src.tags.repository import TagRepository
from src.tags.service import TagService


async def get_tag_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> TagService:
    return TagService(repository=TagRepository(async_session))
