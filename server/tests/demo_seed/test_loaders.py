from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders.featured_users_loader import load_featured_users
from src.demo_seed.loaders.media_queries_loader import load_media_queries
from src.demo_seed.loaders.topics_loader import load_topics


def test_load_source_yaml_files() -> None:
    base = Path("src/demo_seed/data")
    topics = load_topics(base / "topics.yaml")
    featured = load_featured_users(base / "featured_users.yaml")
    media = load_media_queries(base / "media_queries.yaml")

    assert len(topics.topics) == 8
    assert featured.featured_users
    assert media.provider == "pixabay"
