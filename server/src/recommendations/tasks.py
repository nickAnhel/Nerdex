from __future__ import annotations

import asyncio
import logging

from src.assets.celery_app import celery_app
from src.recommendations.sync import run_incremental_sync


logger = logging.getLogger(__name__)


@celery_app.task(name="recommendations.incremental_sync")
def recommendations_incremental_sync_task() -> dict:
    try:
        return asyncio.run(run_incremental_sync())
    except Exception:
        logger.exception("recommendations incremental sync failed")
        raise
