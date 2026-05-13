import uuid
from typing import Any

from sqlalchemy import delete, desc, func, insert, literal_column, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.assets.models import AssetModel, ContentAssetModel, MessageAssetModel
from src.chats.timeline import create_message_timeline_item, get_message_chat_seq
from src.content.models import ContentModel
import src.articles.models  # noqa: F401
import src.moments.models  # noqa: F401
import src.posts.models  # noqa: F401
import src.tags.models  # noqa: F401
import src.videos.models  # noqa: F401
from src.content.enums import ReactionTypeEnum
from src.messages.models import MessageModel, MessageReactionModel, MessageSharedContentModel
from src.users.models import UserModel


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _message_load_options(self):
        return [
            selectinload(MessageModel.user).selectinload(UserModel.subscribers),
            selectinload(MessageModel.user)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants),
            selectinload(MessageModel.reply_to_message).selectinload(MessageModel.user),
            selectinload(MessageModel.reactions),
            self._asset_links_load(),
            *self._shared_content_load(),
        ]

    async def create(
        self,
        data: dict[str, Any],
        asset_ids: list[uuid.UUID] | None = None,
        shared_content_id: uuid.UUID | None = None,
    ) -> MessageModel:
        stmt = (
            insert(MessageModel)
            .values(**data)
            .returning(MessageModel)
            .options(*self._message_load_options())
        )
        result = await self._session.execute(stmt)
        message = result.scalar_one()
        await self._insert_asset_links(message_id=message.message_id, asset_ids=asset_ids or [])
        await self._insert_shared_content(
            message_id=message.message_id,
            content_id=shared_content_id,
        )
        chat_seq = await create_message_timeline_item(
            session=self._session,
            chat_id=message.chat_id,
            message_id=message.message_id,
        )
        await self._session.commit()
        message = await self.get_single(message_id=message.message_id)
        setattr(message, "chat_seq", chat_seq)
        return message

    async def create_idempotent(
        self,
        data: dict[str, Any],
        asset_ids: list[uuid.UUID] | None = None,
        shared_content_id: uuid.UUID | None = None,
    ) -> MessageModel:
        stmt = (
            pg_insert(MessageModel)
            .values(**data)
            .on_conflict_do_nothing(
                constraint="uq_messages_chat_user_client_message_id",
            )
            .returning(MessageModel)
            .options(*self._message_load_options())
        )
        result = await self._session.execute(stmt)
        message = result.scalar_one_or_none()
        if message is None:
            message = await self.get_single(
                chat_id=data["chat_id"],
                user_id=data["user_id"],
                client_message_id=data["client_message_id"],
            )
            chat_seq = await get_message_chat_seq(
                session=self._session,
                message_id=message.message_id,
            )
        else:
            await self._insert_asset_links(message_id=message.message_id, asset_ids=asset_ids or [])
            await self._insert_shared_content(
                message_id=message.message_id,
                content_id=shared_content_id,
            )
            chat_seq = await create_message_timeline_item(
                session=self._session,
                chat_id=message.chat_id,
                message_id=message.message_id,
            )

        await self._session.commit()
        message = await self.get_single(message_id=message.message_id)
        setattr(message, "chat_seq", chat_seq)
        return message

    async def get_single(
        self,
        **filters,
    ) -> MessageModel:
        query = (
            select(MessageModel)
            .filter_by(**filters)
            .execution_options(populate_existing=True)
            .options(*self._message_load_options())
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
            .options(*self._message_load_options())
        )

        result = await self._session.execute(query)
        return list(reversed(result.scalars().all()))

    async def delete(self, **filters) -> int:
        stmt = (
            update(MessageModel)
            .values(deleted_at=func.now(), deleted_by=filters.get("user_id"))
            .filter_by(**filters)
            .where(MessageModel.deleted_at.is_(None))
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount

    async def soft_delete(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MessageModel:
        stmt = (
            update(MessageModel)
            .values(deleted_at=func.now(), deleted_by=user_id)
            .filter_by(message_id=message_id, user_id=user_id)
            .where(MessageModel.deleted_at.is_(None))
            .returning(MessageModel)
            .options(*self._message_load_options())
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def delete_multi(
        self,
        chat_id: uuid.UUID,
    ) -> int:
        stmt = (
            update(MessageModel)
            .values(deleted_at=func.now())
            .filter_by(chat_id=chat_id)
            .where(MessageModel.deleted_at.is_(None))
        )

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
            .values(**data, edited_at=func.now())
            .filter_by(**filters)
            .where(MessageModel.deleted_at.is_(None))
            .returning(MessageModel)
            .options(*self._message_load_options())
        )

        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.scalar_one()

    async def search(
        self,
        query_text: str,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
        **filters,
    ) -> tuple[list[MessageModel], int]:
        search_vector = func.to_tsvector(
            literal_column("'simple'"),
            func.coalesce(MessageModel.content, literal_column("''")),
        )
        search_query = func.websearch_to_tsquery(literal_column("'simple'"), query_text)
        where_clauses = (
            MessageModel.deleted_at.is_(None),
            search_vector.op("@@")(search_query),
        )
        query = (
            select(MessageModel)
            .filter_by(**filters)
            .where(*where_clauses)
            .order_by(
                desc(MessageModel.created_at),
                desc(MessageModel.message_id),
            )
            .offset(offset)
            .limit(limit)
            .options(*self._message_load_options())
        )
        count_query = (
            select(func.count())
            .select_from(MessageModel)
            .filter_by(**filters)
            .where(*where_clauses)
        )

        result = await self._session.execute(query)
        count_result = await self._session.execute(count_query)
        return list(result.scalars().all()), int(count_result.scalar_one())

    async def get_reply_target(
        self,
        *,
        message_id: uuid.UUID,
    ) -> MessageModel:
        query = (
            select(MessageModel)
            .filter_by(message_id=message_id)
            .options(selectinload(MessageModel.user))
        )

        result = await self._session.execute(query)
        return result.scalar_one()

    async def set_reaction(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> MessageModel:
        existing = await self._session.execute(
            select(MessageReactionModel)
            .where(MessageReactionModel.message_id == message_id)
            .where(MessageReactionModel.user_id == user_id)
        )
        current_reaction = existing.scalar_one_or_none()
        if current_reaction is None:
            await self._session.execute(
                insert(MessageReactionModel).values(
                    message_id=message_id,
                    user_id=user_id,
                    reaction_type=reaction_type,
                )
            )
        elif current_reaction.reaction_type != reaction_type:
            await self._session.execute(
                update(MessageReactionModel)
                .where(MessageReactionModel.message_id == message_id)
                .where(MessageReactionModel.user_id == user_id)
                .values(reaction_type=reaction_type)
            )

        await self._session.commit()
        return await self.get_single(message_id=message_id)

    async def remove_reaction(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> MessageModel:
        existing = await self._session.execute(
            select(MessageReactionModel)
            .where(MessageReactionModel.message_id == message_id)
            .where(MessageReactionModel.user_id == user_id)
        )
        current_reaction = existing.scalar_one_or_none()
        if current_reaction is None or current_reaction.reaction_type != reaction_type:
            return await self.get_single(message_id=message_id)

        await self._session.execute(
            delete(MessageReactionModel)
            .where(MessageReactionModel.message_id == message_id)
            .where(MessageReactionModel.user_id == user_id)
        )
        await self._session.commit()
        return await self.get_single(message_id=message_id)

    async def _insert_asset_links(
        self,
        *,
        message_id: uuid.UUID,
        asset_ids: list[uuid.UUID],
    ) -> None:
        if not asset_ids:
            return

        await self._session.execute(
            insert(MessageAssetModel).values(
                [
                    {
                        "message_id": message_id,
                        "asset_id": asset_id,
                        "sort_order": position,
                    }
                    for position, asset_id in enumerate(asset_ids)
                ]
            )
        )

    async def _insert_shared_content(
        self,
        *,
        message_id: uuid.UUID,
        content_id: uuid.UUID | None,
    ) -> None:
        if content_id is None:
            return

        await self._session.execute(
            insert(MessageSharedContentModel).values(
                message_id=message_id,
                content_id=content_id,
            )
        )

    def _asset_links_load(self):
        return (
            selectinload(MessageModel.asset_links)
            .selectinload(MessageAssetModel.asset)
            .selectinload(AssetModel.variants)
        )

    def _shared_content_load(self):
        content_load = selectinload(MessageModel.shared_content).selectinload(
            MessageSharedContentModel.content
        )
        return (
            content_load.selectinload(ContentModel.author).selectinload(UserModel.subscribers),
            content_load.selectinload(ContentModel.author)
            .selectinload(UserModel.avatar_asset)
            .selectinload(AssetModel.variants),
            content_load.selectinload(ContentModel.post_details),
            content_load.selectinload(ContentModel.article_details),
            content_load.selectinload(ContentModel.video_details),
            content_load.selectinload(ContentModel.moment_details),
            content_load.selectinload(ContentModel.video_playback_details),
            content_load.selectinload(ContentModel.tags),
            content_load.selectinload(ContentModel.asset_links)
            .selectinload(ContentAssetModel.asset)
            .selectinload(AssetModel.variants),
        )
