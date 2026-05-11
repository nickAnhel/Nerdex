import uuid
from typing import Any

from sqlalchemy import delete, desc, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.models import AssetModel
from src.messages.models import MessageModel
from src.users.models import UserModel


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: dict[str, Any],
    ) -> MessageModel:
        stmt = (
            insert(MessageModel)
            .values(**data)
            .returning(MessageModel)
            .options(
                selectinload(MessageModel.user).selectinload(UserModel.subscribers),
                selectinload(MessageModel.user)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
            )
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def create_idempotent(
        self,
        data: dict[str, Any],
    ) -> MessageModel:
        stmt = (
            pg_insert(MessageModel)
            .values(**data)
            .on_conflict_do_nothing(
                constraint="uq_messages_chat_user_client_message_id",
            )
            .returning(MessageModel)
            .options(
                selectinload(MessageModel.user).selectinload(UserModel.subscribers),
                selectinload(MessageModel.user)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
            )
        )
        result = await self._session.execute(stmt)
        message = result.scalar_one_or_none()
        if message is None:
            message = await self.get_single(
                chat_id=data["chat_id"],
                user_id=data["user_id"],
                client_message_id=data["client_message_id"],
            )

        await self._session.commit()
        return message

    async def get_single(
        self,
        **filters,
    ) -> MessageModel:
        query = (
            select(MessageModel)
            .filter_by(**filters)
            .options(
                selectinload(MessageModel.user).selectinload(UserModel.subscribers),
                selectinload(MessageModel.user)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
            )
        )

        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_multi(
        self,
        chat_id: uuid.UUID,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[MessageModel]:
        query = (
            select(MessageModel)
            .filter_by(chat_id=chat_id)
            .order_by(desc(order) if order_desc else order)
            .offset(offset)
            .limit(limit)
            .options(
                selectinload(MessageModel.user).selectinload(UserModel.subscribers),
                selectinload(MessageModel.user)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
            )
        )

        result = await self._session.execute(query)
        return list(reversed(result.scalars().all()))

    async def delete(self, **filters) -> int:
        stmt = delete(MessageModel).filter_by(**filters)

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    async def delete_multi(
        self,
        chat_id: uuid.UUID,
    ) -> int:
        stmt = delete(MessageModel).filter_by(chat_id=chat_id)

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    async def update(
        self,
        data: dict[str, Any],
        **filters,
    ) -> MessageModel:
        stmt = (
            update(MessageModel)
            .values(**data)
            .filter_by(**filters)
            .returning(MessageModel)
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def search(
        self,
        q: str,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
        **filters,
    ) -> list[MessageModel]:
        query = (
            select(MessageModel)
            .filter_by(**filters)
            .where(
                MessageModel.content.ilike(f"%{q}%"),
            )
            .order_by(desc(order) if order_desc else order)
            .offset(offset)
            .limit(limit)
            .options(
                selectinload(MessageModel.user).selectinload(UserModel.subscribers),
                selectinload(MessageModel.user)
                .selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants),
            )
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())
