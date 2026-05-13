import uuid

import pytest

from src.chats import typing_state


class FakeRedis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    async def set(self, *args, **kwargs):
        self.calls.append(("set", args, kwargs))

    async def delete(self, *args, **kwargs):
        self.calls.append(("delete", args, kwargs))


@pytest.mark.asyncio
async def test_mark_chat_typing_uses_ttl_and_key_format(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(typing_state, "typing_redis", fake_redis)

    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await typing_state.mark_chat_typing(
        chat_id=chat_id,
        user_id=user_id,
        username="alice",
    )

    assert fake_redis.calls == [
        (
            "set",
            (f"chats:typing:{chat_id}:{user_id}", "alice"),
            {"ex": typing_state.TYPING_STATUS_EXPIRES_IN_SECONDS},
        ),
    ]


@pytest.mark.asyncio
async def test_clear_chat_typing_deletes_key(monkeypatch) -> None:
    fake_redis = FakeRedis()
    monkeypatch.setattr(typing_state, "typing_redis", fake_redis)

    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await typing_state.clear_chat_typing(
        chat_id=chat_id,
        user_id=user_id,
    )

    assert fake_redis.calls == [
        (
            "delete",
            (f"chats:typing:{chat_id}:{user_id}",),
            {},
        ),
    ]
