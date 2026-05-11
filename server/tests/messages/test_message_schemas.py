import datetime
import uuid

from src.messages.schemas import MessageGetWithUser
from src.users.schemas import UserGet


def test_message_get_with_user_preserves_server_created_at() -> None:
    created_at = datetime.datetime.now(datetime.timezone.utc)

    message = MessageGetWithUser(
        message_id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        client_message_id=uuid.uuid4(),
        content="hello",
        user_id=uuid.uuid4(),
        created_at=created_at,
        user=UserGet(
            user_id=uuid.uuid4(),
            username="alice",
            is_admin=False,
            subscribers_count=0,
        ),
    )

    assert message.created_at == created_at
