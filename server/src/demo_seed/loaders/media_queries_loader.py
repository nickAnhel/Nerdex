from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders._yaml import load_yaml
from src.demo_seed.loaders.models import MediaQueriesEnvelope, MediaTopicQueries


def load_media_queries(path: Path) -> MediaQueriesEnvelope:
    data = load_yaml(path)
    topics: dict[str, MediaTopicQueries] = {}
    raw_topics = data.get("topics") or {}
    for topic_slug, item in raw_topics.items():
        topics[topic_slug] = MediaTopicQueries(
            categories=list(item.get("categories") or []),
            image_queries=list(item.get("image_queries") or []),
            video_queries=list(item.get("video_queries") or []),
            moment_queries=list(item.get("moment_queries") or []),
            generated_cover_keywords=list(item.get("generated_cover_keywords") or []),
            negative_keywords=list(item.get("negative_keywords") or []),
        )

    return MediaQueriesEnvelope(
        version=int(data.get("version", 1)),
        provider=str(data.get("provider", "pixabay")),
        defaults=dict(data.get("defaults") or {}),
        topics=topics,
    )
