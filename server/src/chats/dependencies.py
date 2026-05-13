from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage
from src.chats.repository import ChatRepository
from src.chats.service import ChatService
from src.common.database import get_async_session
from src.content.projectors import build_default_content_projector_registry
from src.content.repository import ContentRepository
from src.content.service import ContentService


def get_chat_service(
    session: AsyncSession = Depends(get_async_session),
) -> ChatService:
    storage = get_asset_storage()
    content_projector_registry = build_default_content_projector_registry()
    return ChatService(
        ChatRepository(session),
        storage=storage,
        content_service=ContentService(
            repository=ContentRepository(session),
            asset_storage=storage,
            projector_registry=content_projector_registry,
        ),
    )
