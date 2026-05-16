from __future__ import annotations


TAG_AFFINITY_WEIGHT = 1.0
AUTHOR_AFFINITY_WEIGHT = 1.0
COLLABORATIVE_WEIGHT = 1.0
CONTENT_QUALITY_WEIGHT = 0.2
FRESHNESS_WEIGHT = 6.0
FRESHNESS_DECAY_DAYS = 7.0

COLLABORATIVE_LIKE_WEIGHT = 3.0
COLLABORATIVE_VIEW_WEIGHT = 1.0
COLLABORATIVE_COMMENT_WEIGHT = 2.5


def compute_content_quality_score(
    *,
    likes_count: int,
    dislikes_count: int,
    comments_count: int,
    views_count: int,
) -> float:
    return (
        (likes_count * 4.0)
        - (dislikes_count * 6.0)
        + (comments_count * 5.0)
        + (views_count * 1.0)
    )
