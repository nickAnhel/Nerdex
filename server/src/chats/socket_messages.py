import uuid
from typing import Any

from pydantic import BaseModel

from src.messages.schemas import MessageCreate, MessageCreateWS


class ChatTypingStatusWS(BaseModel):
    chat_id: uuid.UUID
    user_id: uuid.UUID
    username: str
    expires_in_seconds: int


def build_socket_message_create(
    *,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    msg: MessageCreateWS,
) -> MessageCreate:
    return MessageCreate(
        chat_id=chat_id,
        user_id=user_id,
        client_message_id=msg.client_message_id,
        content=msg.content,
        reply_to_message_id=msg.reply_to_message_id,
        asset_ids=msg.asset_ids,
        shared_content_id=msg.shared_content_id,
    )


def build_socket_typing_status(
    *,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    username: str,
    expires_in_seconds: int,
) -> dict[str, Any]:
    return ChatTypingStatusWS(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        expires_in_seconds=expires_in_seconds,
    ).model_dump(mode="json")
