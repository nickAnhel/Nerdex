import datetime
import uuid
from dataclasses import dataclass

import pytest

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.content.schemas import ContentListItemGet
from src.recommendations.graph_repository import RecommendationFeedGraphResult, SimilarContentGraphResult
from src.recommendations.schemas import (
    RecommendationFeedContentTypeEnum,
    RecommendationFeedSortEnum,
    SimilarContentListGet,
)
from src.recommendations.service import RecommendationService
from src.users.schemas import UserGet


@dataclass(slots=True)
class FakeContent:
    content_id: uuid.UUID
    content_type: ContentTypeEnum
    author_id: uuid.UUID


class FakeGraphRepository:
    def __init__(self, rows: list[SimilarContentGraphResult], should_fail: bool = False) -> None:
        self.rows = rows
        self.should_fail = should_fail
        self.calls: list[dict] = []

    async def get_similar_content(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        if self.should_fail:
            raise RuntimeError("neo4j unavailable")
        return self.rows


class FakeGraphFeedRepository(FakeGraphRepository):
    def __init__(
        self,
        rows: list[RecommendationFeedGraphResult],
        should_fail: bool = False,
    ) -> None:
        super().__init__(rows=[], should_fail=should_fail)
        self.feed_rows = rows

    async def get_recommendation_feed(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        if self.should_fail:
            raise RuntimeError("neo4j unavailable")
        return self.feed_rows


class FakePostgresRepository:
    def __init__(
        self,
        hydrated: dict[uuid.UUID, FakeContent],
        fallback_items: list[FakeContent] | None = None,
    ) -> None:
        self.hydrated = hydrated
        self.fallback_items = fallback_items or []
        self.fallback_calls: list[dict] = []

    async def get_visible_content_by_ids(self, *, content_ids, viewer_id):  # type: ignore[no-untyped-def]
        return {
            content_id: self.hydrated[content_id]
            for content_id in content_ids
            if content_id in self.hydrated
        }

    async def get_recommendation_fallback_content(self, **kwargs):  # type: ignore[no-untyped-def]
        self.fallback_calls.append(kwargs)
        return self.fallback_items


class FakeProjector:
    async def project_feed_item(self, content, *, viewer_id, storage):  # type: ignore[no-untyped-def]
        return ContentListItemGet(
            content_id=content.content_id,
            content_type=content.content_type,
            status=ContentStatusEnum.PUBLISHED,
            visibility=ContentVisibilityEnum.PUBLIC,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
            published_at=datetime.datetime.now(datetime.timezone.utc),
            comments_count=0,
            likes_count=0,
            dislikes_count=0,
            views_count=0,
            user=UserGet(
                user_id=content.author_id,
                username="author",
                is_admin=False,
                subscribers_count=0,
                avatar=None,
                avatar_asset_id=None,
            ),
            tags=[],
            my_reaction=None,
            is_owner=content.author_id == viewer_id,
        )


class FakeProjectorRegistry:
    def get(self, content_type):  # type: ignore[no-untyped-def]
        return FakeProjector()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_service_keeps_graph_order_and_drops_non_visible_hydration_rows() -> None:
    viewer_id = uuid.uuid4()
    kept_id = uuid.uuid4()
    hidden_id = uuid.uuid4()

    graph = FakeGraphRepository(
        rows=[
            SimilarContentGraphResult(content_id=hidden_id, score=5.0, reason="shared_tags"),
            SimilarContentGraphResult(content_id=kept_id, score=4.0, reason="shared_audience"),
        ]
    )
    postgres = FakePostgresRepository(
        hydrated={
            kept_id: FakeContent(
                content_id=kept_id,
                content_type=ContentTypeEnum.POST,
                author_id=uuid.uuid4(),
            )
        }
    )

    service = RecommendationService(
        graph_repository=graph,  # type: ignore[arg-type]
        postgres_repository=postgres,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.get_similar_content(
        content_id=uuid.uuid4(),
        viewer_id=viewer_id,
        limit=5,
        content_type=None,
    )

    assert isinstance(response, SimilarContentListGet)
    assert len(response.items) == 1
    assert response.items[0].content_id == kept_id
    assert response.items[0].score == pytest.approx(4.0)


@pytest.mark.anyio
async def test_service_returns_empty_when_graph_unavailable() -> None:
    graph = FakeGraphRepository(rows=[], should_fail=True)
    postgres = FakePostgresRepository(hydrated={})

    service = RecommendationService(
        graph_repository=graph,  # type: ignore[arg-type]
        postgres_repository=postgres,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.get_similar_content(
        content_id=uuid.uuid4(),
        viewer_id=None,
        limit=4,
        content_type=ContentTypeEnum.VIDEO,
    )

    assert response.items == []
    assert response.limit == 4


@pytest.mark.anyio
async def test_recommendations_feed_hydrates_graph_order_and_filters_missing() -> None:
    viewer_id = uuid.uuid4()
    kept_id = uuid.uuid4()
    missing_id = uuid.uuid4()

    graph = FakeGraphFeedRepository(
        rows=[
            RecommendationFeedGraphResult(content_id=missing_id, score=10.0, reason="personalized_graph_feed"),
            RecommendationFeedGraphResult(content_id=kept_id, score=9.0, reason="personalized_graph_feed"),
        ]
    )
    postgres = FakePostgresRepository(
        hydrated={
            kept_id: FakeContent(
                content_id=kept_id,
                content_type=ContentTypeEnum.POST,
                author_id=uuid.uuid4(),
            )
        }
    )
    service = RecommendationService(
        graph_repository=graph,  # type: ignore[arg-type]
        postgres_repository=postgres,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.get_recommendations_feed(
        viewer_id=viewer_id,
        content_type=RecommendationFeedContentTypeEnum.ALL,
        sort=RecommendationFeedSortEnum.RELEVANCE,
        offset=0,
        limit=5,
    )

    assert [item.content_id for item in response] == [kept_id]


@pytest.mark.anyio
async def test_recommendations_feed_uses_fallback_when_graph_fails() -> None:
    fallback_id = uuid.uuid4()
    viewer_id = uuid.uuid4()
    graph = FakeGraphFeedRepository(rows=[], should_fail=True)
    postgres = FakePostgresRepository(
        hydrated={},
        fallback_items=[
            FakeContent(
                content_id=fallback_id,
                content_type=ContentTypeEnum.VIDEO,
                author_id=uuid.uuid4(),
            )
        ],
    )
    service = RecommendationService(
        graph_repository=graph,  # type: ignore[arg-type]
        postgres_repository=postgres,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.get_recommendations_feed(
        viewer_id=viewer_id,
        content_type=RecommendationFeedContentTypeEnum.VIDEO,
        sort=RecommendationFeedSortEnum.NEWEST,
        offset=4,
        limit=3,
    )

    assert [item.content_id for item in response] == [fallback_id]
    assert len(postgres.fallback_calls) == 1
    assert postgres.fallback_calls[0]["offset"] == 4
    assert postgres.fallback_calls[0]["sort"] == "newest"
    assert postgres.fallback_calls[0]["content_type"] == ContentTypeEnum.VIDEO
