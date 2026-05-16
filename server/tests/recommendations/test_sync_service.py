import datetime
import uuid

import pytest

from src.recommendations.postgres_repository import ActivityEventGraphRow
from src.recommendations.sync_service import RecommendationGraphSyncService


class DummyPostgresRepository:
    pass


class DummyGraphRepository:
    pass


def _event(*, action_type: str, content_id: uuid.UUID | None = None, metadata: dict | None = None, target_user_id: uuid.UUID | None = None) -> ActivityEventGraphRow:
    return ActivityEventGraphRow(
        activity_event_id=uuid.uuid4(),
        created_at=datetime.datetime.now(datetime.timezone.utc),
        action_type=action_type,
        user_id=uuid.uuid4(),
        content_id=content_id,
        target_user_id=target_user_id,
        metadata=metadata or {},
    )


def test_event_mapping_tracks_only_supported_recommendation_events() -> None:
    content_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    service = RecommendationGraphSyncService(
        postgres_repository=DummyPostgresRepository(),  # type: ignore[arg-type]
        graph_repository=DummyGraphRepository(),  # type: ignore[arg-type]
    )

    (
        liked_rows,
        disliked_rows,
        remove_liked_rows,
        remove_disliked_rows,
        viewed_rows,
        commented_rows,
        followed_rows,
        unfollowed_rows,
    ) = service._map_events_to_graph_updates([
        _event(action_type="content_like", content_id=content_id),
        _event(action_type="content_dislike", content_id=content_id),
        _event(action_type="content_reaction_removed", content_id=content_id, metadata={"previous_reaction": "like"}),
        _event(action_type="content_reaction_removed", content_id=content_id, metadata={"previous_reaction": "dislike"}),
        _event(action_type="content_reaction_removed", content_id=content_id, metadata={"previous_reaction": "heart"}),
        _event(action_type="content_view", content_id=content_id, metadata={"progress_percent": 96}),
        _event(action_type="content_comment", content_id=content_id),
        _event(action_type="user_follow", target_user_id=target_user_id),
        _event(action_type="user_unfollow", target_user_id=target_user_id),
        _event(action_type="unknown_action", content_id=content_id),
    ])

    assert len(liked_rows) == 1
    assert len(disliked_rows) == 1
    assert len(remove_liked_rows) == 1
    assert len(remove_disliked_rows) == 1
    assert len(viewed_rows) == 1
    assert viewed_rows[0]["progress_percent"] == 96
    assert len(commented_rows) == 1
    assert len(followed_rows) == 1
    assert len(unfollowed_rows) == 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeIncrementalPostgresRepository:
    def __init__(self, events: list[ActivityEventGraphRow]) -> None:
        self._events = events
        self._call_count = 0

    async def get_activity_events_since(self, **kwargs):  # type: ignore[no-untyped-def]
        if self._call_count > 0:
            return []
        self._call_count += 1
        return self._events

    async def get_user_ids_by_ids(self, user_ids):  # type: ignore[no-untyped-def]
        return user_ids

    async def get_content_nodes_by_ids(self, content_ids):  # type: ignore[no-untyped-def]
        return []

    async def get_content_tags_by_content_ids(self, content_ids):  # type: ignore[no-untyped-def]
        return []


class FakeIncrementalGraphRepository:
    def __init__(self) -> None:
        self.follow_rows: list[list[tuple[uuid.UUID, uuid.UUID]]] = []
        self.unfollow_rows: list[list[dict[str, str]]] = []
        self.recompute_affinity_calls: list[list[uuid.UUID]] = []

    async def ensure_schema(self) -> None:
        return None

    async def get_sync_state(self):
        return None

    async def upsert_subscriptions(self, rows):  # type: ignore[no-untyped-def]
        self.follow_rows.append(rows)

    async def remove_follow_edges(self, rows):  # type: ignore[no-untyped-def]
        self.unfollow_rows.append(rows)

    async def set_liked_edges(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def set_disliked_edges(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def remove_liked_edges(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def remove_disliked_edges(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def increment_viewed_edges(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def increment_commented_edges(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def upsert_users(self, user_ids):  # type: ignore[no-untyped-def]
        return None

    async def recompute_interested_in(self, user_ids):  # type: ignore[no-untyped-def]
        return None

    async def recompute_affinity_to_author(self, user_ids):  # type: ignore[no-untyped-def]
        self.recompute_affinity_calls.append(user_ids)

    async def recompute_similar_to(self, content_ids):  # type: ignore[no-untyped-def]
        return None

    async def upsert_sync_state(self, **kwargs):  # type: ignore[no-untyped-def]
        return None

    async def upsert_content_nodes(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def upsert_authored_edges(self, rows):  # type: ignore[no-untyped-def]
        return None

    async def replace_content_tags(self, *, content_ids, tag_rows):  # type: ignore[no-untyped-def]
        return None


@pytest.mark.anyio
async def test_incremental_sync_updates_follow_edges_and_recomputes_affinity() -> None:
    actor_id = uuid.uuid4()
    followed_id = uuid.uuid4()
    unfollowed_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)

    events = [
        ActivityEventGraphRow(
            activity_event_id=uuid.uuid4(),
            created_at=now,
            action_type="user_follow",
            user_id=actor_id,
            content_id=None,
            target_user_id=followed_id,
            metadata={},
        ),
        ActivityEventGraphRow(
            activity_event_id=uuid.uuid4(),
            created_at=now + datetime.timedelta(seconds=1),
            action_type="user_unfollow",
            user_id=actor_id,
            content_id=None,
            target_user_id=unfollowed_id,
            metadata={},
        ),
    ]

    postgres_repository = FakeIncrementalPostgresRepository(events=events)
    graph_repository = FakeIncrementalGraphRepository()
    service = RecommendationGraphSyncService(
        postgres_repository=postgres_repository,  # type: ignore[arg-type]
        graph_repository=graph_repository,  # type: ignore[arg-type]
    )

    await service.incremental_sync()

    assert graph_repository.follow_rows == [[(actor_id, followed_id)]]
    assert graph_repository.unfollow_rows == [[{
        "user_id": str(actor_id),
        "target_user_id": str(unfollowed_id),
    }]]
    assert len(graph_repository.recompute_affinity_calls) == 1
    recomputed_user_ids = set(graph_repository.recompute_affinity_calls[0])
    assert actor_id in recomputed_user_ids
    assert followed_id in recomputed_user_ids
    assert unfollowed_id in recomputed_user_ids
