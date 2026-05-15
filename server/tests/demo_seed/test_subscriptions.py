from __future__ import annotations

import uuid

from src.demo_seed.generators.subscriptions import build_subscriptions
from src.demo_seed.planning.plans import PlannedUser
from src.demo_seed.planning.random_state import SeedRandom


def _user(i: int) -> PlannedUser:
    return PlannedUser(
        user_id=uuid.uuid4(),
        username=f"demo_user_{i}",
        display_name=f"Demo User {i}",
        hashed_password="hash",
        bio="bio",
        links=[],
        is_admin=False,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        interests={"backend": 0.8, "frontend": 0.2 + i * 0.01},
        preferred_content_types={"post": 0.4, "article": 0.3, "video": 0.2, "moment": 0.1},
        expected_tags=["fastapi"],
        role="regular_user",
        is_featured=False,
        presentation_note_en="note",
    )


def test_subscriptions_no_self_and_unique() -> None:
    users = [_user(i) for i in range(20)]
    subscriptions = build_subscriptions(random=SeedRandom(42), users=users, min_count=50, max_count=50)

    pairs = {(row.subscriber_id, row.subscribed_id) for row in subscriptions}
    assert len(pairs) == len(subscriptions)
    assert all(subscriber_id != subscribed_id for subscriber_id, subscribed_id in pairs)
