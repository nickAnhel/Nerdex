from __future__ import annotations

import datetime as dt


def build_seed_report(
    *,
    seed_run_id: str,
    started_at: dt.datetime,
    finished_at: dt.datetime,
    created_counts: dict[str, int],
    media_cache_size_bytes: int,
    uploaded_objects: int,
    skipped_media: int,
    warnings: list[str],
    errors: list[str],
) -> dict:
    return {
        "seed_run_id": seed_run_id,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "created_counts": created_counts,
        "media_cache_size_bytes": media_cache_size_bytes,
        "uploaded_objects": uploaded_objects,
        "skipped_media": skipped_media,
        "warnings": warnings,
        "errors": errors,
    }
