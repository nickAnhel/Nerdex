from __future__ import annotations

import datetime as dt

from src.content.enums import ReactionTypeEnum
from src.demo_seed.planning.graph_plans import topic_overlap_score
from src.demo_seed.planning.plans import (
    PlannedComment,
    PlannedCommentReaction,
    PlannedContent,
    PlannedContentReaction,
    PlannedUser,
)
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.text_plans import build_comment_text
from src.demo_seed.planning.time_distribution import TimeDistributor


def build_content_reactions(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    users: list[PlannedUser],
    contents: list[PlannedContent],
    min_count: int,
    max_count: int,
) -> list[PlannedContentReaction]:
    target = random.randint(min_count, max_count)
    published = [item for item in contents if item.status.value == "published" and item.visibility.value == "public"]
    used: set[tuple[str, str]] = set()
    rows: list[PlannedContentReaction] = []

    weighted_targets: list[tuple[tuple[PlannedUser, PlannedContent], float]] = []
    for user in users:
        for content in published:
            if user.user_id == content.author_id:
                continue
            score = topic_overlap_score(user.interests, {content.topic: 1.0})
            weight = max(0.05, score)
            weighted_targets.append(((user, content), weight))

    while len(rows) < target and weighted_targets:
        user, content = random.weighted_choice(weighted_targets)
        pair = (str(content.content_id), str(user.user_id))
        if pair in used:
            continue
        used.add(pair)
        reaction_type = ReactionTypeEnum.LIKE if random.random() <= 0.86 else ReactionTypeEnum.DISLIKE
        base_time = content.published_at or content.created_at
        created_at = distributor.random_after(base_time, min_minutes=10, max_days=180)
        rows.append(
            PlannedContentReaction(
                content_id=content.content_id,
                user_id=user.user_id,
                reaction_type=reaction_type,
                created_at=created_at,
            )
        )

    return rows


def build_comments(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    users: list[PlannedUser],
    contents: list[PlannedContent],
    min_count: int,
    max_count: int,
) -> list[PlannedComment]:
    target = random.randint(min_count, max_count)
    published = [item for item in contents if item.status.value == "published" and item.visibility.value == "public"]
    comments: list[PlannedComment] = []
    by_content: dict[str, list[PlannedComment]] = {}

    while len(comments) < target and published:
        content = random.choice(published)
        author = random.choice(users)
        if author.user_id == content.author_id and random.random() < 0.3:
            continue

        content_comments = by_content.setdefault(str(content.content_id), [])
        parent = None
        depth = 0
        root_id = None
        reply_to = None
        if content_comments and random.random() <= 0.42:
            parent = random.choice(content_comments)
            depth = min(2, parent.depth + 1)
            root_id = parent.root_comment_id or parent.comment_id
            reply_to = parent.comment_id
            if depth == 2 and parent.depth < 1:
                depth = 1

        created_at = distributor.random_after(content.published_at or content.created_at, min_minutes=5, max_days=240)
        if parent and created_at < parent.created_at:
            created_at = distributor.random_after(parent.created_at, min_minutes=1, max_days=30)

        comment = PlannedComment(
            comment_id=__import__("uuid").uuid4(),
            content_id=content.content_id,
            author_id=author.user_id,
            parent_comment_id=parent.comment_id if parent else None,
            root_comment_id=root_id,
            reply_to_comment_id=reply_to,
            depth=depth,
            body_text=build_comment_text(random, content.topic, content.title),
            created_at=created_at,
            updated_at=created_at,
        )
        comments.append(comment)
        content_comments.append(comment)

    comments.sort(key=lambda item: item.created_at)
    return comments


def build_comment_reactions(
    *,
    random: SeedRandom,
    distributor: TimeDistributor,
    users: list[PlannedUser],
    comments: list[PlannedComment],
    min_count: int,
    max_count: int,
) -> list[PlannedCommentReaction]:
    target = random.randint(min_count, max_count)
    rows: list[PlannedCommentReaction] = []
    used: set[tuple[str, str]] = set()

    while len(rows) < target and comments:
        comment = random.choice(comments)
        user = random.choice(users)
        if user.user_id == comment.author_id:
            continue
        key = (str(comment.comment_id), str(user.user_id))
        if key in used:
            continue
        used.add(key)
        reaction_type = ReactionTypeEnum.LIKE if random.random() <= 0.88 else ReactionTypeEnum.DISLIKE
        created_at = distributor.random_after(comment.created_at, min_minutes=1, max_days=60)
        rows.append(
            PlannedCommentReaction(
                comment_id=comment.comment_id,
                user_id=user.user_id,
                reaction_type=reaction_type,
                created_at=created_at,
            )
        )

    return rows
