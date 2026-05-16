from __future__ import annotations


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
