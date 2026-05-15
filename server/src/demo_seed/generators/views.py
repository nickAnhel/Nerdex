from __future__ import annotations

import datetime as dt
import uuid

from src.content.enums import ContentTypeEnum
from src.demo_seed.planning.plans import PlannedContent, PlannedUser, PlannedViewSession
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.time_distribution import TimeDistributor


def _session_progress(content_type: ContentTypeEnum, random: SeedRandom) -> tuple[int, int, int, int, bool]:
    if content_type == ContentTypeEnum.ARTICLE:
        watched = random.randint(20, 360)
        progress = min(100, random.randint(25, 100))
        counted = progress >= 35 or watched >= 45
        return watched, watched, watched, progress, counted
    if content_type in {ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT}:
        last = random.randint(5, 120)
        watched = random.randint(5, 180)
        progress = min(100, random.randint(10, 100))
        counted = watched >= 15 or progress >= 25
        return last, max(last, watched), watched, progress, counted
    watched = random.randint(5, 80)
    progress = min(100, random.randint(15, 100))
    counted = watched >= 15
    return watched, watched, watched, progress, counted


def build_view_sessions(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    users: list[PlannedUser],
    contents: list[PlannedContent],
    min_count: int,
    max_count: int,
) -> list[PlannedViewSession]:
    target = random.randint(min_count, max_count)
    published = [item for item in contents if item.status.value == "published" and item.visibility.value == "public"]
    rows: list[PlannedViewSession] = []
    counted_by_day: set[tuple[str, str, str]] = set()

    while len(rows) < target and published:
        content = random.choice(published)
        viewer = random.choice(users)
        if viewer.user_id == content.author_id and random.random() < 0.2:
            continue

        started_at = distributor.random_after(content.published_at or content.created_at, min_minutes=1, max_days=330)
        last_position, max_position, watched, progress, counted_candidate = _session_progress(content.content_type, random)
        last_seen_at = distributor.random_after(started_at, min_minutes=1, max_days=1)
        counted_date = last_seen_at.date() if counted_candidate else None
        counted_key = (str(content.content_id), str(viewer.user_id), counted_date.isoformat()) if counted_date else None
        is_counted = bool(counted_candidate and counted_key and counted_key not in counted_by_day)
        if is_counted and counted_key:
            counted_by_day.add(counted_key)

        rows.append(
            PlannedViewSession(
                view_session_id=uuid.uuid4(),
                content_id=content.content_id,
                viewer_id=viewer.user_id,
                started_at=started_at,
                last_seen_at=last_seen_at,
                last_position_seconds=last_position,
                max_position_seconds=max_position,
                watched_seconds=watched,
                progress_percent=progress,
                is_counted=is_counted,
                counted_at=last_seen_at if is_counted else None,
                counted_date=counted_date if is_counted else None,
                source="seed_demo",
                view_metadata={"seed_source": "demo_seed"},
            )
        )

    return rows
