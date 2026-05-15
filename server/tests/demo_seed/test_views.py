from __future__ import annotations

import datetime as dt
import uuid

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.demo_seed.generators.views import build_view_sessions
from src.demo_seed.planning.plans import PlannedContent, PlannedUser
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.time_distribution import TimeDistributor


def _user() -> PlannedUser:
    return PlannedUser(
        user_id=uuid.uuid4(),
        username="demo_user",
        display_name="Demo User",
        hashed_password="hash",
        bio="bio",
        links=[],
        is_admin=False,
        created_at=dt.datetime.now(dt.timezone.utc),
        interests={"backend": 0.9},
        preferred_content_types={"post": 0.4, "article": 0.3, "video": 0.2, "moment": 0.1},
        expected_tags=["fastapi"],
        role="regular_user",
        is_featured=False,
        presentation_note_en="note",
    )


def _content(content_type: ContentTypeEnum) -> PlannedContent:
    now = dt.datetime.now(dt.timezone.utc)
    return PlannedContent(
        content_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        content_type=content_type,
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        title="Title",
        excerpt="Excerpt",
        created_at=now,
        updated_at=now,
        published_at=now,
        content_metadata={"seed_run_id": "x"},
        topic="backend",
        tags=["fastapi"],
        media_asset_ids=[],
        cover_asset_id=None,
        file_asset_ids=[],
    )


def test_counted_view_unique_per_user_content_day() -> None:
    users = [_user() for _ in range(5)]
    contents = [_content(ContentTypeEnum.VIDEO), _content(ContentTypeEnum.ARTICLE)]
    sessions = build_view_sessions(
        random=SeedRandom(13),
        distributor=TimeDistributor(SeedRandom(13)),
        users=users,
        contents=contents,
        min_count=400,
        max_count=400,
    )

    counted_keys = set()
    for session in sessions:
        if not session.is_counted:
            continue
        key = (session.content_id, session.viewer_id, session.counted_date)
        assert key not in counted_keys
        counted_keys.add(key)
