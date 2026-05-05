from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.assets.celery_app import celery_app
from src.assets.repository import AssetRepository
from src.assets.service import AssetService
from src.assets.storage import AssetStorage
from src.common.model_registry import import_all_models
from src.config import settings
from src.videos.repository import VideoRepository
from src.videos.service import VideoAssetProcessingNotifier


import_all_models()


def _build_task_session_maker() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        url=settings.db.db_url,
        echo=settings.db.echo,
        poolclass=NullPool,
    )
    return engine, async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def enqueue_image_processing(asset_id: uuid.UUID) -> None:
    process_image_asset_task.delay(str(asset_id))


def enqueue_video_processing(asset_id: uuid.UUID) -> None:
    process_video_asset_task.delay(str(asset_id))


async def _run_with_service(
    handler,  # type: ignore[no-untyped-def]
):
    engine, session_maker = _build_task_session_maker()
    try:
        async with session_maker() as session:
            service = AssetService(
                repository=AssetRepository(session),
                storage=AssetStorage(settings.storage),
                settings=settings.assets,
                video_processing_notifier=VideoAssetProcessingNotifier(VideoRepository(session)),
            )
            return await handler(service)
    finally:
        await engine.dispose()


@celery_app.task(name="assets.process_image_asset")
def process_image_asset_task(asset_id: str) -> None:
    asyncio.run(
        _run_with_service(
            lambda service: service.process_image_asset(asset_id=uuid.UUID(asset_id))
        )
    )


@celery_app.task(name="assets.process_video_asset")
def process_video_asset_task(asset_id: str) -> None:
    asyncio.run(
        _run_with_service(
            lambda service: service.process_video_asset(asset_id=uuid.UUID(asset_id))
        )
    )


@celery_app.task(name="assets.cleanup_stale_uploads")
def cleanup_stale_uploads_task() -> None:
    asyncio.run(_run_with_service(lambda service: service.cleanup_stale_uploads()))


@celery_app.task(name="assets.cleanup_orphaned_assets")
def cleanup_orphaned_assets_task() -> None:
    asyncio.run(_run_with_service(lambda service: service.cleanup_orphaned_assets()))


@celery_app.task(name="assets.reconcile_failed_assets")
def reconcile_failed_assets_task() -> None:
    asyncio.run(_run_with_service(lambda service: service.reconcile_failed_assets()))
