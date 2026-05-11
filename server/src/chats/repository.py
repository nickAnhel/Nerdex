import uuid
from typing import Any

from sqlalchemy import delete, desc, func, insert, literal, or_, select, union, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.models import AssetModel
from src.chats.enums import ChatMemberRole, ChatType
from src.chats.models import ChatModel, MembershipModel
from src.events.models import EventModel
from src.messages.models import MessageModel
from src.users.models import UserModel


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: dict[str, Any],
    ) -> ChatModel:
        stmt = (
            insert(ChatModel)
            .values(**data)
            .returning(ChatModel)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def create_with_member_roles(
        self,
        *,
        data: dict[str, Any],
        member_roles: list[tuple[uuid.UUID, ChatMemberRole]],
    ) -> ChatModel:
        try:
            chat_result = await self._session.execute(
                insert(ChatModel)
                .values(**data)
                .returning(ChatModel)
            )
            chat = chat_result.scalar_one()

            if member_roles:
                await self._session.execute(
                    insert(MembershipModel).values(
                        [
                            {
                                "chat_id": chat.chat_id,
                                "user_id": user_id,
                                "role": role.value,
                            }
                            for user_id, role in member_roles
                        ]
                    )
                )

            await self._session.commit()
            return chat
        except Exception:
            await self._session.rollback()
            raise

    async def get_single(
        self,
        **filters,
    ) -> ChatModel:
        query = (
            select(ChatModel)
            .filter_by(**filters)
            .options(self._members_load())
        )

        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_by_direct_key(
        self,
        direct_key: str,
    ) -> ChatModel | None:
        query = (
            select(ChatModel)
            .filter_by(chat_type=ChatType.DIRECT.value, direct_key=direct_key)
            .options(self._members_load())
        )

        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def history(
        self,
        *,
        chat_id: uuid.UUID,
        offset: int,
        limit: int,
    ) -> list[MessageModel | EventModel]:
        msgs_query = (
            select(MessageModel.message_id.label("id"), MessageModel.created_at)
            .filter_by(chat_id=chat_id)
        )

        events_query = (
            select(EventModel.event_id.label("id"), EventModel.created_at)
            .filter_by(chat_id=chat_id)
        )

        union_query = (
            union(
                msgs_query,
                events_query,
            )
            .order_by(desc("created_at"))
            .offset(offset)
            .limit(limit)
            .cte()
        )

        q1  = (
            select(MessageModel)
            .join(union_query, MessageModel.message_id == union_query.c.id)
            .options(selectinload(MessageModel.user))
        )

        q2 = (
            select(EventModel)
            .join(union_query, EventModel.event_id == union_query.c.id)
            .options(selectinload(EventModel.user))
            .options(selectinload(EventModel.altered_user))
        )

        messages: list[MessageModel] = (await self._session.execute(q1)).scalars().all()  # type: ignore
        events: list[EventModel] = (await self._session.execute(q2)).scalars().all()  # type: ignore

        history = messages + events
        return sorted(history, key=lambda item: item.created_at)

    async def get_members(
        self,
        chat_id: uuid.UUID,
    ) -> list[UserModel]:
        query = (
            select(UserModel)
            .join(MembershipModel, MembershipModel.user_id == UserModel.user_id)
            .where(MembershipModel.chat_id == chat_id)
            .options(
                selectinload(UserModel.avatar_asset)
                .selectinload(AssetModel.variants)
            )
        )

        result = await self._session.execute(query)
        members = list(result.scalars().all())
        if not members:
            await self.get_single(chat_id=chat_id)
        return members

    async def is_member(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        query = (
            select(MembershipModel.user_id)
            .filter_by(chat_id=chat_id, user_id=user_id)
            .limit(1)
        )

        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    async def is_owner_member(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        query = (
            select(MembershipModel.user_id)
            .filter_by(
                chat_id=chat_id,
                user_id=user_id,
                role=ChatMemberRole.OWNER.value,
            )
            .limit(1)
        )

        result = await self._session.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_multi(
        self,
        *,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ChatModel]:
        query = (
            select(ChatModel)
            .filter_by(is_private=False, chat_type=ChatType.GROUP.value)
            .options(self._members_load())
            .order_by(desc(order) if order_desc else order)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def add_members(
        self,
        chat_id: uuid.UUID,
        users_ids: list[uuid.UUID],
        role: ChatMemberRole = ChatMemberRole.MEMBER,
    ) -> int:
        users_query = (
            select(literal(chat_id), UserModel.user_id, literal(role.value))
            .where(
                UserModel.user_id.in_([user_id for user_id in users_ids]),
            )
        )

        stmt = (
            insert(MembershipModel)
            .from_select(
                ["chat_id", "user_id", "role"],
                users_query,
            )
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    async def remove_members(
        self,
        chat_id: uuid.UUID,
        members_ids: list[uuid.UUID],
    ) -> int:
        stmt = (
            delete(MembershipModel)
            .filter_by(chat_id=chat_id)
            .where(MembershipModel.user_id.in_(members_ids))
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    async def update(
        self,
        chat_id: uuid.UUID,
        data: dict[str, Any],
    ) -> ChatModel:
        stmt = (
            update(ChatModel)
            .values(**data)
            .filter_by(chat_id=chat_id)
            .returning(ChatModel)
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def delete(
        self,
        chat_id: uuid.UUID,
    ) -> int:
        stmt = (
            delete(ChatModel)
            .filter_by(chat_id=chat_id)
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    async def search(
        self,
        *,
        user_id: uuid.UUID,
        q: str,
        offset: int,
        limit: int,
    ) -> list[ChatModel]:
        subquery = (
            select(ChatModel.chat_id)
            .where(
                ChatModel.title.bool_op("%")(q),
                ChatModel.chat_type == ChatType.GROUP.value,
                or_(
                    ChatModel.is_private == False,
                    ChatModel.members.contains(UserModel(user_id=user_id)),
                ),
            )
            .distinct()
            .subquery()
        )

        query = (
            select(ChatModel)
            .join(subquery, ChatModel.chat_id == subquery.c.chat_id)
            .options(self._members_load())
            .order_by(
                func.similarity(ChatModel.title, q).desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())


    async def get_user_joined_chats(
        self,
        user_id: uuid.UUID,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ChatModel]:
        chat_ids_query = (
            select(MembershipModel.chat_id)
            .filter_by(user_id=user_id)
            .cte()
        )

        query = (
            select(ChatModel)
            .where(ChatModel.chat_id.in_(chat_ids_query))
            .options(self._members_load())
            .order_by(desc(order) if order_desc else order)
            .offset(offset)
            .limit(limit)
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    def _members_load(self):
        return (
            selectinload(ChatModel.members)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants)
        )
