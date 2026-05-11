import uuid

from src.messages.schemas import MessageCreate, MessageCreateWS


def build_socket_message_create(
    *,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    msg: MessageCreateWS,
) -> MessageCreate:
    return MessageCreate(
        chat_id=chat_id,
        user_id=user_id,
        content=msg.content,
        created_at=msg.created_at.replace(tzinfo=None),
    )
