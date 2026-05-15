from __future__ import annotations

from collections import defaultdict

from src.demo_seed.loaders.models import TopicDefinition, TopicsConfig
from src.demo_seed.planning.random_state import SeedRandom


def build_interest_vector(
    random: SeedRandom,
    topics: TopicsConfig,
    primary_topic: str | None = None,
) -> dict[str, float]:
    values: dict[str, float] = {}
    for topic_slug in topics.topics:
        base = random.uniform(0.05, 0.45)
        values[topic_slug] = base

    if primary_topic and primary_topic in values:
        values[primary_topic] = random.uniform(0.82, 0.98)

    if primary_topic and primary_topic in topics.topics:
        topic = topics.topics[primary_topic]
        for adjacent_slug, weight in topic.adjacent_topics.items():
            if adjacent_slug in values:
                values[adjacent_slug] = max(values[adjacent_slug], round(weight * random.uniform(0.5, 0.95), 3))

    return {k: round(v, 3) for k, v in values.items()}


def build_topic_weights_for_author(interests: dict[str, float], topics: TopicsConfig) -> list[tuple[str, float]]:
    weighted: list[tuple[str, float]] = []
    for topic_slug, topic in topics.topics.items():
        weighted.append((topic_slug, interests.get(topic_slug, 0.1) * topic.weight))
    return weighted


def pick_tags_for_topic(
    random: SeedRandom,
    topic: TopicDefinition,
    min_tags: int = 2,
    max_tags: int = 4,
) -> list[str]:
    count = random.randint(min_tags, max_tags)
    weighted = [(tag.slug, tag.weight) for tag in topic.tags]
    selected: list[str] = []
    pool = weighted.copy()
    while pool and len(selected) < count:
        tag_slug = random.weighted_choice(pool)
        selected.append(tag_slug)
        pool = [(slug, weight) for slug, weight in pool if slug != tag_slug]
    return selected


def derive_expected_tags(interests: dict[str, float], topics: TopicsConfig, top_k: int = 8) -> list[str]:
    scored: dict[str, float] = defaultdict(float)
    for topic_slug, score in interests.items():
        if topic_slug not in topics.topics:
            continue
        for tag in topics.topics[topic_slug].tags:
            scored[tag.slug] += score * tag.weight
    ranked = sorted(scored.items(), key=lambda item: item[1], reverse=True)
    return [slug for slug, _ in ranked[:top_k]]
