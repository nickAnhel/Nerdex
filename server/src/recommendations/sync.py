from __future__ import annotations

import argparse
import asyncio
import json

from src.common.database import async_session_maker
from src.common.model_registry import import_all_models
from src.config import settings
from src.observability import configure_logging
from src.recommendations.graph_repository import RecommendationGraphRepository, create_neo4j_driver
from src.recommendations.postgres_repository import RecommendationPostgresRepository
from src.recommendations.sync_service import RecommendationGraphSyncService

configure_logging()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.recommendations.sync",
        description="Recommendation graph sync CLI",
    )
    parser.add_argument(
        "command",
        choices=["full-rebuild", "incremental-sync"],
    )
    return parser


async def run_full_rebuild() -> dict:
    import_all_models()

    async with async_session_maker() as session:
        driver = create_neo4j_driver()
        await _wait_for_neo4j(driver=driver, database=settings.neo4j.database)
        graph_repository = RecommendationGraphRepository(
            driver=driver,
            database=settings.neo4j.database,
        )
        try:
            service = RecommendationGraphSyncService(
                postgres_repository=RecommendationPostgresRepository(session),
                graph_repository=graph_repository,
            )
            return await service.full_rebuild()
        finally:
            await graph_repository.close()


async def run_incremental_sync() -> dict:
    import_all_models()

    async with async_session_maker() as session:
        driver = create_neo4j_driver()
        await _wait_for_neo4j(driver=driver, database=settings.neo4j.database)
        graph_repository = RecommendationGraphRepository(
            driver=driver,
            database=settings.neo4j.database,
        )
        try:
            service = RecommendationGraphSyncService(
                postgres_repository=RecommendationPostgresRepository(session),
                graph_repository=graph_repository,
            )
            return await service.incremental_sync()
        finally:
            await graph_repository.close()


async def _wait_for_neo4j(*, driver, database: str, attempts: int = 30, delay_seconds: float = 1.0) -> None:  # type: ignore[no-untyped-def]
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            await driver.verify_connectivity()
            async with driver.session(database=database) as session:
                await session.run("RETURN 1")
            return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(delay_seconds)
    if last_error is not None:
        raise last_error


async def run_cli_async(args: argparse.Namespace) -> int:
    if args.command == "full-rebuild":
        result = await run_full_rebuild()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "incremental-sync":
        result = await run_incremental_sync()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 1


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run_cli_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
