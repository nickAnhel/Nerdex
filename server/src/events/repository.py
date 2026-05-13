import uuid
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.chats.timeline import create_event_timeline_item
from src.events.models import EventModel


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        data: dict[str, Any],
    ) -> EventModel:
        stmt = (
            insert(EventModel)
            .values(**data)
            .returning(EventModel)
        )

        result = await self._session.execute(stmt)
        event = result.scalar_one()
        chat_seq = await create_event_timeline_item(
            session=self._session,
            chat_id=event.chat_id,
            event_id=event.event_id,
        )
        await self._session.commit()
        setattr(event, "chat_seq", chat_seq)
        return event

    async def get_multi(
        self,
        *,
        chat_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> list[EventModel]:
        query = (
            select(EventModel)
            .filter_by(chat_id=chat_id)
            .order_by(EventModel.created_at.desc())
            .offset(offset)
            .limit(limit)
            .options(selectinload(EventModel.user))
            .options(selectinload(EventModel.altered_user))
        )
        result = await self._session.execute(query)
        return list(reversed((result.scalars().all())))
