from __future__ import annotations

from src.demo_seed.loaders.models import TopicsConfig


def collect_tag_slugs(topics: TopicsConfig) -> list[str]:
    slugs: list[str] = []
    for topic in topics.topics.values():
        for tag in topic.tags:
            slugs.append(tag.slug)
    return sorted(set(slugs))
