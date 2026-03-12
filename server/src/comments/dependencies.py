from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.comments.repository import CommentRepository
from src.comments.service import CommentService
from src.common.database import get_async_session


async def get_comment_service(
    async_session: AsyncSession = Depends(get_async_session),
) -> CommentService:
    return CommentService(repository=CommentRepository(async_session))
