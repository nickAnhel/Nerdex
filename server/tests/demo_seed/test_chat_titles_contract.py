from __future__ import annotations

import datetime as dt
import uuid

from src.chats.enums import ChatType
from src.demo_seed.generators.chats import CHAT_TITLE_MAX_LENGTH, build_chats
from src.demo_seed.planning.plans import PlannedUser
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.time_distribution import TimeDistributor


def _make_user(index: int, display_name: str) -> PlannedUser:
    return PlannedUser(
        user_id=uuid.uuid4(),
        username=f"demo_user_{index}",
        display_name=display_name,
        hashed_password="hash",
        bio="bio",
        links=[],
        is_admin=False,
        created_at=dt.datetime.now(dt.timezone.utc),
        interests={"backend": 1.0},
        preferred_content_types={"post": 1.0},
        expected_tags=["fastapi"],
        role="regular_user",
        is_featured=False,
        presentation_note_en="note",
    )


def test_chat_titles_fit_schema_length() -> None:
    users = [
        _make_user(1, "Alexandria Verylongname Backend Specialist 001"),
        _make_user(2, "Benjamin Extra Long Display Name For Demo User 002"),
        _make_user(3, "Catherine Longname Platform Reliability Engineer 003"),
        _make_user(4, "Dmitry Very Long Name Data Infrastructure Architect 004"),
    ]
    seed_run_id = "seed-20260515101010-42"
    plan = build_chats(
        random=SeedRandom(42),
        distributor=TimeDistributor(SeedRandom(42)),
        users=users,
        seed_run_id=seed_run_id,
        min_count=3,
        max_count=3,
    )

    assert plan.chats
    assert any(chat.chat_type == ChatType.DIRECT.value for chat in plan.chats)
    assert all(chat.title.startswith(f"[DEMO:{seed_run_id}] ") for chat in plan.chats)
    assert all(len(chat.title) <= CHAT_TITLE_MAX_LENGTH for chat in plan.chats)
