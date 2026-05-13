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
        client_message_id=msg.client_message_id,
        content=msg.content,
        reply_to_message_id=msg.reply_to_message_id,
        asset_ids=msg.asset_ids,
        shared_content_id=msg.shared_content_id,
    )
