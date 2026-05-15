from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders.topics_loader import load_topics
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.text_plans import build_article_text, build_video_text


def test_article_toc_uses_text_key() -> None:
    topics = load_topics(Path("src/demo_seed/data/topics.yaml"))
    topic = topics.topics["backend"]

    _, _, _, _, _, toc, _ = build_article_text(
        SeedRandom(42),
        topic,
        angle=topic.content_angles[0],
        tags=["fastapi"],
    )

    assert toc
    assert all("text" in item for item in toc)
    assert all("title" not in item for item in toc)


def test_video_chapters_use_starts_at_seconds_key() -> None:
    topics = load_topics(Path("src/demo_seed/data/topics.yaml"))
    topic = topics.topics["backend"]

    _, _, _, chapters = build_video_text(
        SeedRandom(42),
        topic,
        angle=topic.content_angles[0],
        tags=["fastapi"],
    )

    assert chapters
    assert all("startsAtSeconds" in chapter for chapter in chapters)
    assert all("timestamp_seconds" not in chapter for chapter in chapters)
