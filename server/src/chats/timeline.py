import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.chats.models import ChatModel, ChatTimelineItemModel


async def allocate_chat_seq(
    *,
    session: AsyncSession,
    chat_id: uuid.UUID,
) -> int:
    stmt = (
        update(ChatModel)
        .where(ChatModel.chat_id == chat_id)
        .values(last_timeline_seq=ChatModel.last_timeline_seq + 1)
        .returning(ChatModel.last_timeline_seq)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def create_message_timeline_item(
    *,
    session: AsyncSession,
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
) -> int:
    chat_seq = await allocate_chat_seq(session=session, chat_id=chat_id)
    await session.execute(
        insert(ChatTimelineItemModel).values(
            chat_id=chat_id,
            chat_seq=chat_seq,
            item_type="message",
            message_id=message_id,
        )
    )
    return chat_seq


async def create_event_timeline_item(
    *,
    session: AsyncSession,
    chat_id: uuid.UUID,
    event_id: uuid.UUID,
) -> int:
    chat_seq = await allocate_chat_seq(session=session, chat_id=chat_id)
    await session.execute(
        insert(ChatTimelineItemModel).values(
            chat_id=chat_id,
            chat_seq=chat_seq,
            item_type="event",
            event_id=event_id,
        )
    )
    return chat_seq


async def get_message_chat_seq(
    *,
    session: AsyncSession,
    message_id: uuid.UUID,
) -> int | None:
    result = await session.execute(
        select(ChatTimelineItemModel.chat_seq)
        .where(ChatTimelineItemModel.message_id == message_id)
        .limit(1)
    )
    return result.scalar_one_or_none()
