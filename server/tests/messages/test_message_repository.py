import datetime
import asyncio
import uuid

import pytest
from sqlalchemy.dialects import postgresql

from src.common.model_registry import import_all_models
from src.messages.models import MessageModel
from src.messages.repository import MessageRepository

import_all_models()


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def all(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class _Session:
    def __init__(self, results) -> None:
        self.results = list(results)
        self.committed = False
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
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
    session = _Session([None, message, 7, message])
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


@pytest.mark.asyncio
async def test_get_single_refreshes_loaded_relationships() -> None:
    message = MessageModel(
        message_id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="hello",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session = _Session([message])
    repository = MessageRepository(session)  # type: ignore[arg-type]

    result = await repository.get_single(message_id=message.message_id)

    assert result is message
    assert session.statements[-1].get_execution_options()["populate_existing"] is True


def test_search_uses_full_text_query_and_chat_scope() -> None:
    message = MessageModel(
        message_id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        content="hello world",
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    session = _Session([[message], 1])
    repository = MessageRepository(session)  # type: ignore[arg-type]

    result = asyncio.run(
        repository.search(
            query_text="hello",
            order="created_at",
            order_desc=True,
            offset=5,
            limit=20,
            chat_id=message.chat_id,
        )
    )

    sql = str(
        session.statements[-2].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    count_sql = str(
        session.statements[-1].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert result == ([message], 1)
    assert "websearch_to_tsquery('simple', 'hello')" in sql
    assert "to_tsvector('simple', coalesce(messages.content, ''))" in sql
    assert "messages.deleted_at IS NULL" in sql
    assert "messages.chat_id = " in sql
    assert "ORDER BY messages.created_at DESC, messages.message_id DESC" in sql
    assert "count(*)" in count_sql.lower()
    assert "messages.deleted_at IS NULL" in count_sql
