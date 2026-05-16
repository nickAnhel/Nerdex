import uuid

import pytest

from src.auth.dependencies import get_current_optional_user
from src.content.enums import ContentTypeEnum
from src.recommendations.router import get_recommendations_feed, get_similar_content, router
from src.recommendations.schemas import (
    RecommendationFeedContentTypeEnum,
    RecommendationFeedSortEnum,
    SimilarContentListGet,
)
from src.users.schemas import UserGet


class FakeRecommendationService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def get_similar_content(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return SimilarContentListGet(items=[], limit=kwargs["limit"])

    async def get_recommendations_feed(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return []


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_recommendations_route_uses_optional_user_dependency() -> None:
    route = next(route for route in router.routes if getattr(route, "path", None) == "/recommendations/content/{content_id}/similar")
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}

    assert get_current_optional_user in dependency_calls


@pytest.mark.anyio
async def test_similar_endpoint_passes_filters_to_service() -> None:
    viewer = UserGet(
        user_id=uuid.uuid4(),
        username="viewer",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
    )
    service = FakeRecommendationService()
    content_id = uuid.uuid4()

    response = await get_similar_content(
        content_id=content_id,
        limit=6,
        content_type=ContentTypeEnum.VIDEO,
        user=viewer,
        recommendation_service=service,  # type: ignore[arg-type]
    )

    assert response.limit == 6
    assert response.items == []

    call = service.calls[0]
    assert call["content_id"] == content_id
    assert call["viewer_id"] == viewer.user_id
    assert call["limit"] == 6
    assert call["content_type"] == ContentTypeEnum.VIDEO


@pytest.mark.anyio
async def test_recommendations_feed_endpoint_passes_filters_to_service() -> None:
    viewer = UserGet(
        user_id=uuid.uuid4(),
        username="viewer",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
    )
    service = FakeRecommendationService()

    response = await get_recommendations_feed(
        content_type=RecommendationFeedContentTypeEnum.VIDEO,
        sort=RecommendationFeedSortEnum.NEWEST,
        offset=10,
        limit=5,
        user=viewer,
        recommendation_service=service,  # type: ignore[arg-type]
    )

    assert response == []
    call = service.calls[0]
    assert call["viewer_id"] == viewer.user_id
    assert call["content_type"] == RecommendationFeedContentTypeEnum.VIDEO
    assert call["sort"] == RecommendationFeedSortEnum.NEWEST
    assert call["offset"] == 10
    assert call["limit"] == 5
