import datetime
import uuid

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
        _event(action_type="content_view", content_id=content_id),
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
    assert len(commented_rows) == 1
    assert len(followed_rows) == 1
    assert len(unfollowed_rows) == 1
