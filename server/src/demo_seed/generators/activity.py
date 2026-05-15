from __future__ import annotations

import uuid

from src.activity.enums import ActivityActionTypeEnum
from src.demo_seed.planning.plans import (
    PlannedActivityEvent,
    PlannedComment,
    PlannedCommentReaction,
    PlannedContent,
    PlannedContentReaction,
    PlannedSubscription,
    PlannedViewSession,
)
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.time_distribution import TimeDistributor


def build_activity_events(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    contents_by_id: dict[uuid.UUID, PlannedContent],
    subscriptions: list[PlannedSubscription],
    content_reactions: list[PlannedContentReaction],
    comments: list[PlannedComment],
    comment_reactions: list[PlannedCommentReaction],
    view_sessions: list[PlannedViewSession],
    min_count: int,
    max_count: int,
    seed_run_id: str,
) -> list[PlannedActivityEvent]:
    rows: list[PlannedActivityEvent] = []

    for row in subscriptions:
        rows.append(
            PlannedActivityEvent(
                activity_event_id=uuid.uuid4(),
                user_id=row.subscriber_id,
                action_type=ActivityActionTypeEnum.USER_FOLLOW.value,
                content_id=None,
                target_user_id=row.subscribed_id,
                comment_id=None,
                content_type=None,
                created_at=distributor.random_content_created_at(),
                event_metadata={"seed_run_id": seed_run_id},
            )
        )

    for reaction in content_reactions:
        content = contents_by_id.get(reaction.content_id)
        rows.append(
            PlannedActivityEvent(
                activity_event_id=uuid.uuid4(),
                user_id=reaction.user_id,
                action_type=(
                    ActivityActionTypeEnum.CONTENT_LIKE.value
                    if reaction.reaction_type.value == "like"
                    else ActivityActionTypeEnum.CONTENT_DISLIKE.value
                ),
                content_id=reaction.content_id,
                target_user_id=content.author_id if content else None,
                comment_id=None,
                content_type=content.content_type if content else None,
                created_at=reaction.created_at,
                event_metadata={"seed_run_id": seed_run_id},
            )
        )

    for comment in comments:
        content = contents_by_id.get(comment.content_id)
        rows.append(
            PlannedActivityEvent(
                activity_event_id=uuid.uuid4(),
                user_id=comment.author_id,
                action_type=ActivityActionTypeEnum.CONTENT_COMMENT.value,
                content_id=comment.content_id,
                target_user_id=content.author_id if content else None,
                comment_id=comment.comment_id,
                content_type=content.content_type if content else None,
                created_at=comment.created_at,
                event_metadata={"seed_run_id": seed_run_id},
            )
        )

    for session in view_sessions:
        content = contents_by_id.get(session.content_id)
        rows.append(
            PlannedActivityEvent(
                activity_event_id=uuid.uuid4(),
                user_id=session.viewer_id,
                action_type=ActivityActionTypeEnum.CONTENT_VIEW.value,
                content_id=session.content_id,
                target_user_id=content.author_id if content else None,
                comment_id=None,
                content_type=content.content_type if content else None,
                created_at=session.last_seen_at,
                event_metadata={"seed_run_id": seed_run_id, "counted": session.is_counted},
            )
        )

    target = random.randint(min_count, max_count)
    if len(rows) < target:
        extra = target - len(rows)
        sample_pool = rows[:]
        for _ in range(extra):
            base = random.choice(sample_pool)
            rows.append(
                PlannedActivityEvent(
                    activity_event_id=uuid.uuid4(),
                    user_id=base.user_id,
                    action_type=base.action_type,
                    content_id=base.content_id,
                    target_user_id=base.target_user_id,
                    comment_id=base.comment_id,
                    content_type=base.content_type,
                    created_at=distributor.random_after(base.created_at, min_minutes=1, max_days=3),
                    event_metadata={"seed_run_id": seed_run_id, "synthetic": True},
                )
            )

    rows.sort(key=lambda item: item.created_at)
    return rows
