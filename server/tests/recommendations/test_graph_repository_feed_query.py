import uuid

import pytest

from src.recommendations.graph_repository import RecommendationGraphRepository


class DummyDriver:
    pass


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_feed_query_contains_required_visibility_and_exclusion_filters() -> None:
    repository = RecommendationGraphRepository(driver=DummyDriver(), database="neo4j")
    captured: dict = {}

    async def fake_read(query, parameters=None):  # type: ignore[no-untyped-def]
        captured["query"] = query
        captured["parameters"] = parameters or {}
        return [
            {
                "content_id": str(uuid.uuid4()),
                "score": 12.5,
                "reason": "personalized_graph_feed",
            }
        ]

    repository._read = fake_read  # type: ignore[method-assign]

    await repository.get_recommendation_feed(
        viewer_id=uuid.uuid4(),
        content_type="video",
        sort="relevance",
        offset=0,
        limit=10,
    )

    query = captured["query"]
    assert "candidate.status = 'published'" in query
    assert "candidate.visibility = 'public'" in query
    assert "candidate.author_id <> viewer.user_id" in query
    assert "MATCH (viewer)-[:DISLIKED]->(candidate)" in query
    assert "coalesce(seen.progress_percent, 0) >= 90" in query
    assert captured["parameters"]["content_type"] == "video"
    assert captured["parameters"]["sort"] == "relevance"


@pytest.mark.anyio
async def test_feed_query_accepts_anonymous_viewer() -> None:
    repository = RecommendationGraphRepository(driver=DummyDriver(), database="neo4j")
    captured: dict = {}

    async def fake_read(query, parameters=None):  # type: ignore[no-untyped-def]
        captured["parameters"] = parameters or {}
        return []

    repository._read = fake_read  # type: ignore[method-assign]

    rows = await repository.get_recommendation_feed(
        viewer_id=None,
        content_type=None,
        sort="newest",
        offset=5,
        limit=7,
    )

    assert rows == []
    assert captured["parameters"]["viewer_id"] is None
    assert captured["parameters"]["content_type"] is None
    assert captured["parameters"]["sort"] == "newest"
    assert captured["parameters"]["offset"] == 5
    assert captured["parameters"]["limit"] == 7
