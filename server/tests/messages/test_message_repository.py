import datetime
import uuid

import pytest

from src.common.model_registry import import_all_models
from src.messages.models import MessageModel
from src.messages.repository import MessageRepository

import_all_models()


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _Session:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.committed = False

    async def execute(self, _stmt):
        return _Result(self.results.pop(0))

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_idempotent_duplicate_message_reuses_existing_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_id = uuid.uuid4()
    user_id = uuid.uuid4()
    client_message_id = uuid.uuid4()
    message = MessageModel(
        message_id=uuid.uuid4(),
        chat_id=chat_id,
        user_id=user_id,
        client_message_id=client_message_id,
        content="hello",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session = _Session([None, message, 7])
    created_timeline_items = []

    async def fake_create_message_timeline_item(**kwargs):
        created_timeline_items.append(kwargs)
        return 8

    monkeypatch.setattr(
        "src.messages.repository.create_message_timeline_item",
        fake_create_message_timeline_item,
    )

    repository = MessageRepository(session)  # type: ignore[arg-type]
    result = await repository.create_idempotent(
        {
            "chat_id": chat_id,
            "user_id": user_id,
            "client_message_id": client_message_id,
            "content": "hello",
        }
    )

    assert result is message
    assert result.chat_seq == 7
    assert created_timeline_items == []
    assert session.committed is True
