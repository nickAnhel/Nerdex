from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_async_session
from src.events.repository import EventRepository
from src.events.service import EventService


async def get_event_service(
    session: AsyncSession = Depends(get_async_session),
) -> EventService:
    return EventService(EventRepository(session))
