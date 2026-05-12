from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.assets.dependencies import get_asset_storage
from src.assets.repository import AssetRepository
from src.common.database import get_async_session
from src.messages.repository import MessageRepository
from src.messages.service import MessageService


def get_message_service(
    session: AsyncSession = Depends(get_async_session),
) -> MessageService:
    return MessageService(
        repostory=MessageRepository(session),
        asset_repository=AssetRepository(session),
        storage=get_asset_storage(),
    )
