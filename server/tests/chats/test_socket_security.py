import uuid

import pytest
import socketio
from sqlalchemy.exc import NoResultFound

from src.chats import sockets
from src.chats.exceptions import ChatNotFound
from src.chats.service import ChatService
from src.chats.socket_messages import build_socket_message_create
from src.common.exceptions import PermissionDenied
from src.messages.schemas import MessageCreateWS


class FakeChatRepository:
    def __init__(self, *, is_member: bool, chat_exists: bool = True) -> None:
        self._is_member = is_member
        self._chat_exists = chat_exists

    async def is_member(self, *, chat_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        return self._is_member

    async def get_single(self, **filters):
        if not self._chat_exists:
            raise NoResultFound

        return object()


def test_socket_server_uses_redis_manager() -> None:
    assert isinstance(sockets.sio.manager, socketio.AsyncRedisManager)
    assert sockets.sio.manager.redis_url == sockets.settings.redis.socketio_manager_url


@pytest.mark.asyncio
async def test_ensure_user_is_chat_member_allows_participant() -> None:
    service = ChatService(FakeChatRepository(is_member=True))  # type: ignore[arg-type]

    await service.ensure_user_is_chat_member(
        chat_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_ensure_user_is_chat_member_rejects_non_participant() -> None:
    service = ChatService(FakeChatRepository(is_member=False))  # type: ignore[arg-type]

    with pytest.raises(PermissionDenied):
        await service.ensure_user_is_chat_member(
            chat_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_ensure_user_is_chat_member_reports_missing_chat() -> None:
    service = ChatService(FakeChatRepository(is_member=False, chat_exists=False))  # type: ignore[arg-type]

    with pytest.raises(ChatNotFound):
        await service.ensure_user_is_chat_member(
            chat_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
        )


def test_socket_message_create_uses_authenticated_user_id() -> None:
    chat_id = uuid.uuid4()
    authenticated_user_id = uuid.uuid4()
    spoofed_user_id = uuid.uuid4()
    msg = MessageCreateWS.model_validate(
        {
            "chat_id": chat_id,
            "client_message_id": uuid.uuid4(),
            "content": "hello",
            "user_id": spoofed_user_id,
        }
    )

    result = build_socket_message_create(
        chat_id=chat_id,
        user_id=authenticated_user_id,
        msg=msg,
    )

    assert result.chat_id == chat_id
    assert result.user_id == authenticated_user_id
    assert result.user_id != spoofed_user_id
    assert result.content == "hello"
    assert result.client_message_id == msg.client_message_id


def test_socket_message_create_does_not_accept_client_created_at() -> None:
    msg = MessageCreateWS.model_validate(
        {
            "chat_id": uuid.uuid4(),
            "client_message_id": uuid.uuid4(),
            "content": "hello",
            "created_at": "1999-01-01T00:00:00Z",
        }
    )

    result = build_socket_message_create(
        chat_id=msg.chat_id,
        user_id=uuid.uuid4(),
        msg=msg,
    )

    assert not hasattr(result, "created_at")
