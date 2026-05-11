from sqlalchemy.orm import configure_mappers
from sqlalchemy.pool import NullPool


def test_asset_tasks_import_all_relationship_models() -> None:
    import src.assets.tasks  # noqa: F401

    configure_mappers()


def test_asset_tasks_use_non_pooled_asyncpg_connections() -> None:
    from src.assets.tasks import _build_task_session_maker

    engine, _ = _build_task_session_maker()
    try:
        assert isinstance(engine.sync_engine.pool, NullPool)
    finally:
        engine.sync_engine.dispose()
