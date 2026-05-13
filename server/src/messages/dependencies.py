from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage
from src.assets.repository import AssetRepository
from src.chats.repository import ChatRepository
from src.common.database import get_async_session
from src.content.projectors import build_default_content_projector_registry
from src.content.repository import ContentRepository
from src.content.service import ContentService
from src.messages.repository import MessageRepository
from src.messages.service import MessageService


def get_message_service(
    session: AsyncSession = Depends(get_async_session),
) -> MessageService:
    storage = get_asset_storage()
    content_projector_registry = build_default_content_projector_registry()
    content_service = ContentService(
        repository=ContentRepository(session),
        asset_storage=storage,
        projector_registry=content_projector_registry,
    )
    return MessageService(
        repostory=MessageRepository(session),
        asset_repository=AssetRepository(session),
        storage=storage,
        chat_repository=ChatRepository(session),
        content_service=content_service,
    )
