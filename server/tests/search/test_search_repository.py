import datetime
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from src.content.enums import ContentTypeEnum
from src.search.enums import SearchSortEnum
from src.search.repository import SearchRepository


class FakeResult:
    def __init__(self, rows):  # type: ignore[no-untyped-def]
        self._rows = rows

    def all(self):
        return self._rows


class CapturingSession:
    def __init__(self, rows_queue):  # type: ignore[no-untyped-def]
        self.rows_queue = list(rows_queue)
        self.statements = []

    async def execute(self, stmt):  # type: ignore[no-untyped-def]
        self.statements.append(stmt)
        rows = self.rows_queue.pop(0) if self.rows_queue else []
        return FakeResult(rows)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _compile_sql(stmt) -> str:  # type: ignore[no-untyped-def]
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.anyio
async def test_search_content_applies_public_ready_visibility_filters() -> None:
    content_id_1 = uuid.uuid4()
    content_id_2 = uuid.uuid4()
    session = CapturingSession(
        [[
            SimpleNamespace(content_id=content_id_1, score=0.93, sort_timestamp=datetime.datetime.now(datetime.timezone.utc)),
            SimpleNamespace(content_id=content_id_2, score=0.75, sort_timestamp=datetime.datetime.now(datetime.timezone.utc)),
        ]]
    )
    repository = SearchRepository(session)  # type: ignore[arg-type]

    matches, has_more = await repository.search_content(
        query_text="python async",
        content_type=ContentTypeEnum.POST,
        sort=SearchSortEnum.RELEVANCE,
        offset=0,
        limit=1,
    )

    assert has_more is True
    assert [match.content_id for match in matches] == [content_id_1]

    sql = _compile_sql(session.statements[0])
    assert "content.status = 'published'" in sql
    assert "content.visibility = 'public'" in sql
    assert "content.deleted_at IS NULL" in sql
    assert "video_playback_details.processing_status = 'ready'" in sql
    assert "content.content_type = 'post'" in sql
    assert "search_vector @@ websearch_to_tsquery('simple', 'python async')" in sql


@pytest.mark.anyio
async def test_search_all_uses_union_for_mixed_results() -> None:
    content_id = uuid.uuid4()
    author_id = uuid.uuid4()
    session = CapturingSession(
        [[
            SimpleNamespace(
                result_type="content",
                content_id=content_id,
                author_id=None,
                score=0.86,
                sort_timestamp=datetime.datetime.now(datetime.timezone.utc),
            ),
            SimpleNamespace(
                result_type="author",
                content_id=None,
                author_id=author_id,
                score=0.61,
                sort_timestamp=datetime.datetime.now(datetime.timezone.utc),
            ),
        ]]
    )
    repository = SearchRepository(session)  # type: ignore[arg-type]

    matches, has_more = await repository.search_all(
        query_text="creator",
        sort=SearchSortEnum.NEWEST,
        offset=0,
        limit=10,
    )

    assert has_more is False
    assert [match.result_type for match in matches] == ["content", "author"]
    sql = _compile_sql(session.statements[0])
    assert "UNION ALL" in sql
    assert "FROM content" in sql
    assert "FROM users" in sql


@pytest.mark.anyio
async def test_search_authors_uses_user_search_vector_and_newest_sort() -> None:
    author_id = uuid.uuid4()
    session = CapturingSession(
        [[
            SimpleNamespace(
                author_id=author_id,
                score=0.72,
                sort_timestamp=datetime.datetime.now(datetime.timezone.utc),
            )
        ]]
    )
    repository = SearchRepository(session)  # type: ignore[arg-type]

    matches, has_more = await repository.search_authors(
        query_text="alex",
        sort=SearchSortEnum.NEWEST,
        offset=5,
        limit=10,
    )

    assert has_more is False
    assert matches[0].author_id == author_id

    sql = _compile_sql(session.statements[0])
    assert "to_tsvector('simple'" in sql
    assert "users.created_at DESC" in sql
    assert "OFFSET 5" in sql
