from __future__ import annotations

from pathlib import Path

from src.demo_seed.loaders.topics_loader import load_topics
from src.demo_seed.planning.affinity import build_interest_vector
from src.demo_seed.planning.random_state import SeedRandom


def test_interest_vector_deterministic_for_seed() -> None:
    topics = load_topics(Path("src/demo_seed/data/topics.yaml"))
    one = build_interest_vector(SeedRandom(42), topics, primary_topic="backend")
    two = build_interest_vector(SeedRandom(42), topics, primary_topic="backend")
    assert one == two
