from __future__ import annotations

import datetime as dt

from src.demo_seed.reports.seed_report import build_seed_report


def test_seed_report_build() -> None:
    started_at = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    finished_at = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)
    report = build_seed_report(
        seed_run_id="seed-1",
        started_at=started_at,
        finished_at=finished_at,
        created_counts={"users": 10},
        media_cache_size_bytes=123,
        uploaded_objects=5,
        skipped_media=1,
        warnings=[],
        errors=[],
    )
    assert report["seed_run_id"] == "seed-1"
    assert report["created_counts"]["users"] == 10
