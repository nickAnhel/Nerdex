from __future__ import annotations

from src.demo_seed.planning.graph_plans import topic_overlap_score
from src.demo_seed.planning.plans import PlannedSubscription, PlannedUser
from src.demo_seed.planning.random_state import SeedRandom


def build_subscriptions(
    *,
    random: SeedRandom,
    users: list[PlannedUser],
    min_count: int,
    max_count: int,
) -> list[PlannedSubscription]:
    target = random.randint(min_count, max_count)
    pairs: set[tuple[str, str]] = set()
    users_list = list(users)

    weighted_pairs: list[tuple[tuple[PlannedUser, PlannedUser], float]] = []
    for left in users_list:
        for right in users_list:
            if left.user_id == right.user_id:
                continue
            score = topic_overlap_score(left.interests, right.interests)
            weight = max(0.05, score)
            if right.role in {"active_author", "popular_author"}:
                weight *= 1.35
            weighted_pairs.append(((left, right), weight))

    while len(pairs) < target and weighted_pairs:
        left, right = random.weighted_choice(weighted_pairs)
        pair_key = (str(left.user_id), str(right.user_id))
        if pair_key in pairs:
            continue
        pairs.add(pair_key)

    return [
        PlannedSubscription(
            subscriber_id=next(user.user_id for user in users_list if str(user.user_id) == subscriber_id),
            subscribed_id=next(user.user_id for user in users_list if str(user.user_id) == subscribed_id),
        )
        for subscriber_id, subscribed_id in sorted(pairs)
    ]
