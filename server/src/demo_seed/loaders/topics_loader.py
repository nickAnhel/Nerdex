from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders._yaml import load_yaml
from src.demo_seed.loaders.models import TopicDefinition, TopicTag, TopicsConfig


def load_topics(path: Path) -> TopicsConfig:
    data = load_yaml(path)
    topics: dict[str, TopicDefinition] = {}
    raw_topics = data.get("topics") or {}
    for topic_slug, payload in raw_topics.items():
        tags = [
            TopicTag(
                slug=item["slug"],
                title=item.get("title", item["slug"]),
                weight=float(item.get("weight", 1.0)),
            )
            for item in payload.get("tags", [])
        ]
        topics[topic_slug] = TopicDefinition(
            slug=topic_slug,
            title=payload.get("title", topic_slug),
            description=payload.get("description", ""),
            weight=float(payload.get("weight", 1.0)),
            tags=tags,
            adjacent_topics={k: float(v) for k, v in (payload.get("adjacent_topics") or {}).items()},
            content_angles=list(payload.get("content_angles") or []),
        )

    return TopicsConfig(version=int(data.get("version", 1)), topics=topics)
