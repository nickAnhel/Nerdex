import uuid

from sqlalchemy.exc import IntegrityError, NoResultFound

from src.chats.exceptions import ChatNotFound
from src.messages.exceptions import CantDeleteMessage, CantUpdateMessage, InvalidMessageReply
from src.messages.repository import MessageRepository
from src.messages.schemas import (
    MessageCreate,
    MessageGet,
    MessageGetWithUser,
    MessageReplyPreview,
    MessageUpdate,
)
from src.users.presentation import build_user_get

DELETED_MESSAGE_STUB = "Message deleted"


class MessageService:
    def __init__(self, repostory: MessageRepository) -> None:
        self._repository = repostory

    async def create_message(
        self,
        message: MessageCreate,
    ) -> MessageGetWithUser:
        try:
            if message.reply_to_message_id is not None:
                await self._ensure_reply_target_belongs_to_chat(
                    reply_to_message_id=message.reply_to_message_id,
                    chat_id=message.chat_id,
                )

            data = message.model_dump()
            if message.client_message_id is not None:
                msg = await self._repository.create_idempotent(data=data)
            else:
                msg = await self._repository.create(data=data)
            return await self._build_message_with_user(msg)
        except (IntegrityError, NoResultFound) as exc:
            raise ChatNotFound(f"Chat with id '{message.chat_id}' not found") from exc

    async def get_messages(
        self,
        *,
        chat_id: uuid.UUID,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[MessageGetWithUser]:
        messages = await self._repository.get_multi(
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
            chat_id=chat_id,
        )
        return [await self._build_message_with_user(message) for message in messages]

    async def delete_message(
        self,
        *,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> MessageGetWithUser:
        try:
            message = await self._repository.soft_delete(
                message_id=message_id,
                user_id=user_id,
            )
        except NoResultFound as exc:
            raise CantDeleteMessage(
                f"Message with id '{message_id}' and user_id '{user_id}' not found"
            ) from exc

        return await self._build_message_with_user(message)

    async def delete_messages(
        self,
        *,
        chat_id: uuid.UUID,
    ) -> int:
        return await self._repository.delete_multi(chat_id=chat_id)

    async def update_message(
        self,
        *,
        data: MessageUpdate,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MessageGetWithUser:
        try:
            message = await self._repository.update(
                data=data.model_dump(exclude_none=True),
                message_id=message_id,
                user_id=user_id,
            )
        except NoResultFound as exc:
            raise CantUpdateMessage(
                f"Message with id '{message_id}' and user_id '{user_id}' not found"
            ) from exc

        return await self._build_message_with_user(message)

    async def udpate_message(
        self,
        *,
        data: MessageUpdate,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MessageGetWithUser:
        return await self.update_message(
            data=data,
            message_id=message_id,
            user_id=user_id,
        )

    async def _ensure_reply_target_belongs_to_chat(
        self,
        *,
        reply_to_message_id: uuid.UUID,
        chat_id: uuid.UUID,
    ) -> None:
        try:
            reply_target = await self._repository.get_reply_target(
                message_id=reply_to_message_id,
            )
        except NoResultFound as exc:
            raise InvalidMessageReply(
                f"Reply target message with id '{reply_to_message_id}' not found"
            ) from exc

        if reply_target.chat_id != chat_id:
            raise InvalidMessageReply(
                f"Reply target message with id '{reply_to_message_id}' belongs to another chat"
            )

    async def search_messages(
        self,
        *,
        chat_id: uuid.UUID,
        query: str,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[MessageGetWithUser]:
        messages = await self._repository.search(
            q=query,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
            chat_id=chat_id,
        )
        return [await self._build_message_with_user(message) for message in messages]

    async def _build_message_with_user(
        self,
        message,
    ) -> MessageGetWithUser:
        reply_to_message = getattr(message, "reply_to_message", None)
        return MessageGetWithUser(
            message_id=message.message_id,
            chat_id=message.chat_id,
            client_message_id=message.client_message_id,
            content=(
                DELETED_MESSAGE_STUB
                if message.deleted_at is not None
                else message.content
            ),
            user_id=message.user_id,
            created_at=message.created_at,
            edited_at=message.edited_at,
            deleted_at=message.deleted_at,
            deleted_by=message.deleted_by,
            chat_seq=getattr(message, "chat_seq", None),
            reply_to_message_id=getattr(message, "reply_to_message_id", None),
            reply_preview=(
                self._build_reply_preview(reply_to_message)
                if reply_to_message is not None
                else None
            ),
            user=await build_user_get(message.user),
        )

    def _build_reply_preview(self, message) -> MessageReplyPreview:
        deleted = message.deleted_at is not None
        return MessageReplyPreview(
            message_id=message.message_id,
            sender_display_name=message.user.username,
            content_preview=DELETED_MESSAGE_STUB if deleted else message.content_ellipsis,
            deleted=deleted,
        )
