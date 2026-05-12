import datetime
import uuid

from src.messages.schemas import MessageGetWithUser, MessageReplyPreview
from src.users.schemas import UserGet


def test_message_get_with_user_preserves_server_created_at() -> None:
    created_at = datetime.datetime.now(datetime.timezone.utc)
    edited_at = created_at + datetime.timedelta(minutes=1)
    deleted_at = created_at + datetime.timedelta(minutes=2)
    deleted_by = uuid.uuid4()
    reply_to_message_id = uuid.uuid4()

    message = MessageGetWithUser(
        message_id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        client_message_id=uuid.uuid4(),
        content="hello",
        user_id=uuid.uuid4(),
        created_at=created_at,
        edited_at=edited_at,
        deleted_at=deleted_at,
        deleted_by=deleted_by,
        reply_to_message_id=reply_to_message_id,
        reply_preview=MessageReplyPreview(
            message_id=reply_to_message_id,
            sender_display_name="bob",
            content_preview="reply preview",
            deleted=False,
        ),
        user=UserGet(
            user_id=uuid.uuid4(),
            username="alice",
            is_admin=False,
            subscribers_count=0,
        ),
    )

    assert message.created_at == created_at
    assert message.edited_at == edited_at
    assert message.deleted_at == deleted_at
    assert message.deleted_by == deleted_by
    assert message.reply_to_message_id == reply_to_message_id
    assert message.reply_preview is not None
    assert message.reply_preview.content_preview == "reply preview"
