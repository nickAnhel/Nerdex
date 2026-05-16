import datetime
import uuid
from dataclasses import dataclass

import pytest

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.content.schemas import ContentListItemGet
from src.recommendations.graph_repository import SimilarContentGraphResult
from src.recommendations.schemas import SimilarContentListGet
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


class FakePostgresRepository:
    def __init__(self, hydrated: dict[uuid.UUID, FakeContent]) -> None:
        self.hydrated = hydrated

    async def get_visible_content_by_ids(self, *, content_ids, viewer_id):  # type: ignore[no-untyped-def]
        return {
            content_id: self.hydrated[content_id]
            for content_id in content_ids
            if content_id in self.hydrated
        }


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
