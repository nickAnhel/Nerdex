from __future__ import annotations

from collections import defaultdict
from typing import Iterable


def topic_overlap_score(left: dict[str, float], right: dict[str, float]) -> float:
    score = 0.0
    for topic_slug, left_weight in left.items():
        score += min(left_weight, right.get(topic_slug, 0.0))
    return score


def build_author_topic_index(user_rows: Iterable[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = defaultdict(list)
    for row in user_rows:
        for topic_slug, score in row.get("interests", {}).items():
            if score >= 0.55:
                result[topic_slug].append(row)
    return dict(result)
