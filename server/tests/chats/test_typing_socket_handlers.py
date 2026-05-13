import uuid
from unittest.mock import AsyncMock

import pytest

from src.chats import sockets
from src.common.exceptions import PermissionDenied


class DummySessionManager:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeChatService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def ensure_user_is_chat_member(self, *, chat_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.calls.append((chat_id, user_id))
        if self.error is not None:
            raise self.error


@pytest.mark.asyncio
async def test_typing_start_marks_state_and_broadcasts_to_chat(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    fake_service = FakeChatService()
    emit = AsyncMock()
    mark_chat_typing = AsyncMock()

    monkeypatch.setattr(sockets, "_get_socket_user_context", AsyncMock(return_value=(user_id, "alice")))
    monkeypatch.setattr(sockets, "async_session_maker", lambda: DummySessionManager(object()))
    monkeypatch.setattr(sockets, "get_chat_service", lambda session: fake_service)
    monkeypatch.setattr(sockets.typing_state, "mark_chat_typing", mark_chat_typing)
    monkeypatch.setattr(sockets.sio, "emit", emit)

    result = await sockets.on_typing_start("sid-1", {"chat_id": str(chat_id)})

    assert result == {"ok": True, "data": {"expires_in_seconds": sockets.typing_state.TYPING_STATUS_EXPIRES_IN_SECONDS}}
    assert fake_service.calls == [(chat_id, user_id)]
    mark_chat_typing.assert_awaited_once_with(
        chat_id=chat_id,
        user_id=user_id,
        username="alice",
    )
    emit.assert_awaited_once()
    assert emit.await_args.args == (
        "typing:start",
        {
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "username": "alice",
            "expires_in_seconds": sockets.typing_state.TYPING_STATUS_EXPIRES_IN_SECONDS,
        },
    )
    assert emit.await_args.kwargs == {
        "room": str(chat_id),
        "skip_sid": "sid-1",
    }


@pytest.mark.asyncio
async def test_typing_stop_clears_state_and_broadcasts_stop(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    fake_service = FakeChatService()
    emit = AsyncMock()
    clear_chat_typing = AsyncMock()

    monkeypatch.setattr(sockets, "_get_socket_user_context", AsyncMock(return_value=(user_id, "alice")))
    monkeypatch.setattr(sockets, "async_session_maker", lambda: DummySessionManager(object()))
    monkeypatch.setattr(sockets, "get_chat_service", lambda session: fake_service)
    monkeypatch.setattr(sockets.typing_state, "clear_chat_typing", clear_chat_typing)
    monkeypatch.setattr(sockets.sio, "emit", emit)

    result = await sockets.on_typing_stop("sid-1", {"chat_id": str(chat_id)})

    assert result == {"ok": True}
    assert fake_service.calls == [(chat_id, user_id)]
    clear_chat_typing.assert_awaited_once_with(
        chat_id=chat_id,
        user_id=user_id,
    )
    emit.assert_awaited_once()
    assert emit.await_args.args == (
        "typing:stop",
        {
            "chat_id": str(chat_id),
            "user_id": str(user_id),
            "username": "alice",
            "expires_in_seconds": sockets.typing_state.TYPING_STATUS_EXPIRES_IN_SECONDS,
        },
    )
    assert emit.await_args.kwargs == {
        "room": str(chat_id),
        "skip_sid": "sid-1",
    }


@pytest.mark.asyncio
async def test_typing_start_rejects_non_member(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    fake_service = FakeChatService(error=PermissionDenied("Forbidden"))
    emit = AsyncMock()
    mark_chat_typing = AsyncMock()

    monkeypatch.setattr(sockets, "_get_socket_user_context", AsyncMock(return_value=(user_id, "alice")))
    monkeypatch.setattr(sockets, "async_session_maker", lambda: DummySessionManager(object()))
    monkeypatch.setattr(sockets, "get_chat_service", lambda session: fake_service)
    monkeypatch.setattr(sockets.typing_state, "mark_chat_typing", mark_chat_typing)
    monkeypatch.setattr(sockets.sio, "emit", emit)

    result = await sockets.on_typing_start("sid-1", {"chat_id": str(chat_id)})

    assert result["ok"] is False
    assert result["error"]["code"] == "forbidden"
    mark_chat_typing.assert_not_awaited()
    emit.assert_not_awaited()
