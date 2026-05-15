from __future__ import annotations

import pytest
from sqlalchemy import Column, Integer, MetaData, Table

from src.demo_seed.writers.seed_bulk_repository import SeedBulkRepository
from src.demo_seed.writers.seed_cleanup_repository import _iter_chunks


class _DummySession:
    def __init__(self) -> None:
        self.statements = []

    async def execute(self, statement):  # type: ignore[no-untyped-def]
        self.statements.append(statement)
        return None


def test_iter_chunks_splits_large_lists() -> None:
    values = list(range(25))
    chunks = list(_iter_chunks(values, 10))
    assert chunks == [list(range(10)), list(range(10, 20)), list(range(20, 25))]


@pytest.mark.asyncio
async def test_flush_chunks_respects_max_query_arguments() -> None:
    session = _DummySession()
    repository = SeedBulkRepository(session)  # type: ignore[arg-type]

    metadata = MetaData()
    test_table = Table(
        "seed_chunk_test",
        metadata,
        *[Column(f"c{index}", Integer) for index in range(20)],
    )
    rows = [{f"c{index}": index for index in range(20)} for _ in range(3201)]

    await repository.flush_chunks(test_table, rows, chunk_size=2000)

    chunk_lengths = [len(statement._multi_values[0]) for statement in session.statements]  # noqa: SLF001
    assert chunk_lengths == [1600, 1600, 1]
