from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.chats.repository import ChatRepository
from src.chats.service import ChatService
from src.database import get_async_session


def get_chat_service(
    session: AsyncSession = Depends(get_async_session),
) -> ChatService:
    return ChatService(ChatRepository(session))
