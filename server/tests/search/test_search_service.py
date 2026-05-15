import datetime
import uuid
from dataclasses import dataclass, field

import pytest

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.content.schemas import ContentListItemGet
from src.search.enums import SearchContentTypeEnum, SearchPopularPeriodEnum, SearchSortEnum, SearchTypeEnum
from src.search.repository import SearchAuthorMatch, SearchContentMatch, SearchMixedMatch
from src.search.service import SearchService
from src.users.schemas import UserGet


@dataclass
class FakeUser:
    user_id: uuid.UUID
    username: str
    display_name: str | None = None
    bio: str | None = None
    links: list[dict] = field(default_factory=list)
    avatar_asset_id: uuid.UUID | None = None
    avatar_crop: dict | None = None
    subscribers_count: int = 0
    is_admin: bool = False
    subscribers: list = field(default_factory=list)
    avatar_asset = None


@dataclass
class FakeContent:
    content_id: uuid.UUID
    content_type: ContentTypeEnum
    author: UserGet
    status: ContentStatusEnum = ContentStatusEnum.PUBLISHED
    visibility: ContentVisibilityEnum = ContentVisibilityEnum.PUBLIC
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    published_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    comments_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    views_count: int = 0
    tags: list = field(default_factory=list)
    my_reaction: str | None = None
    is_owner: bool = False


class FakeProjector:
    async def project_feed_item(self, item, *, viewer_id, storage):  # type: ignore[no-untyped-def]
        return ContentListItemGet(
            content_id=item.content_id,
            content_type=item.content_type,
            status=item.status,
            visibility=item.visibility,
            created_at=item.created_at,
            updated_at=item.updated_at,
            published_at=item.published_at,
            comments_count=item.comments_count,
            likes_count=item.likes_count,
            dislikes_count=item.dislikes_count,
            views_count=item.views_count,
            user=item.author,
            tags=item.tags,
            my_reaction=item.my_reaction,
            is_owner=item.is_owner,
        )


class FakeProjectorRegistry:
    def get(self, content_type):  # type: ignore[no-untyped-def]
        return FakeProjector()


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.content_matches: list[SearchContentMatch] = []
        self.author_matches: list[SearchAuthorMatch] = []
        self.mixed_matches: list[SearchMixedMatch] = []
        self.content_map: dict[uuid.UUID, FakeContent] = {}
        self.user_map: dict[uuid.UUID, FakeUser] = {}
        self.has_more_content = False
        self.has_more_authors = False
        self.has_more_all = False
        self.has_more_popular = False

    async def search_content(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("search_content", kwargs))
        return self.content_matches, self.has_more_content

    async def search_authors(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("search_authors", kwargs))
        return self.author_matches, self.has_more_authors

    async def search_all(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("search_all", kwargs))
        return self.mixed_matches, self.has_more_all

    async def search_popular_content(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(("search_popular_content", kwargs))
        return self.content_matches, self.has_more_popular

    async def get_content_by_ids(self, *, content_ids, viewer_id):  # type: ignore[no-untyped-def]
        self.calls.append(("get_content_by_ids", {"content_ids": content_ids, "viewer_id": viewer_id}))
        return {content_id: self.content_map[content_id] for content_id in content_ids if content_id in self.content_map}

    async def get_users_by_ids(self, *, user_ids):  # type: ignore[no-untyped-def]
        self.calls.append(("get_users_by_ids", {"user_ids": user_ids}))
        return {user_id: self.user_map[user_id] for user_id in user_ids if user_id in self.user_map}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_search_authors_returns_author_items() -> None:
    viewer_id = uuid.uuid4()
    user_id = uuid.uuid4()

    repository = FakeRepository()
    repository.author_matches = [SearchAuthorMatch(author_id=user_id, score=0.91)]
    repository.user_map[user_id] = FakeUser(
        user_id=user_id,
        username="alpha",
        subscribers=[FakeUser(user_id=viewer_id, username="viewer")],
    )

    service = SearchService(
        repository=repository,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.search(
        query="alpha",
        search_type=SearchTypeEnum.AUTHOR,
        sort=SearchSortEnum.RELEVANCE,
        offset=0,
        limit=20,
        viewer_id=viewer_id,
    )

    assert len(response.items) == 1
    assert response.items[0].result_type == "author"
    assert response.items[0].author is not None
    assert response.items[0].author.username == "alpha"
    assert response.items[0].author.is_subscribed is True
    assert response.items[0].score == pytest.approx(0.91)


@pytest.mark.anyio
async def test_search_all_returns_mixed_items_in_order() -> None:
    viewer_id = uuid.uuid4()
    author = UserGet(
        user_id=uuid.uuid4(),
        username="writer",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
    )
    content_id = uuid.uuid4()
    author_id = uuid.uuid4()

    repository = FakeRepository()
    repository.mixed_matches = [
        SearchMixedMatch(result_type="content", content_id=content_id, author_id=None, score=0.88),
        SearchMixedMatch(result_type="author", content_id=None, author_id=author_id, score=0.77),
    ]
    repository.content_map[content_id] = FakeContent(content_id=content_id, content_type=ContentTypeEnum.POST, author=author)
    repository.user_map[author_id] = FakeUser(user_id=author_id, username="creator")

    service = SearchService(
        repository=repository,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.search(
        query="creator",
        search_type=SearchTypeEnum.ALL,
        sort=SearchSortEnum.RELEVANCE,
        offset=0,
        limit=20,
        viewer_id=viewer_id,
    )

    assert [item.result_type for item in response.items] == ["content", "author"]
    assert response.items[0].content is not None
    assert response.items[0].content.content_id == content_id
    assert response.items[1].author is not None
    assert response.items[1].author.username == "creator"


@pytest.mark.anyio
async def test_search_post_type_uses_content_mapping() -> None:
    viewer_id = uuid.uuid4()
    author = UserGet(
        user_id=uuid.uuid4(),
        username="writer",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
    )
    content_id = uuid.uuid4()

    repository = FakeRepository()
    repository.content_matches = [SearchContentMatch(content_id=content_id, score=0.66)]
    repository.content_map[content_id] = FakeContent(content_id=content_id, content_type=ContentTypeEnum.POST, author=author)

    service = SearchService(
        repository=repository,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.search(
        query="post",
        search_type=SearchTypeEnum.POST,
        sort=SearchSortEnum.NEWEST,
        offset=5,
        limit=10,
        viewer_id=viewer_id,
    )

    assert len(response.items) == 1
    assert response.items[0].result_type == "content"
    assert response.items[0].content is not None
    assert response.items[0].content.content_id == content_id

    search_call = next(call for call in repository.calls if call[0] == "search_content")
    assert search_call[1]["content_type"] == ContentTypeEnum.POST
    assert search_call[1]["sort"] == SearchSortEnum.NEWEST
    assert search_call[1]["offset"] == 5
    assert search_call[1]["limit"] == 10


@pytest.mark.anyio
async def test_search_popular_uses_popular_repository_and_allows_negative_scores() -> None:
    viewer_id = uuid.uuid4()
    author = UserGet(
        user_id=uuid.uuid4(),
        username="writer",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
    )
    content_id = uuid.uuid4()

    repository = FakeRepository()
    repository.content_matches = [SearchContentMatch(content_id=content_id, score=-2.0)]
    repository.content_map[content_id] = FakeContent(content_id=content_id, content_type=ContentTypeEnum.POST, author=author)

    service = SearchService(
        repository=repository,  # type: ignore[arg-type]
        projector_registry=FakeProjectorRegistry(),  # type: ignore[arg-type]
        asset_storage=None,
    )

    response = await service.search_popular(
        search_type=SearchContentTypeEnum.POST,
        period=SearchPopularPeriodEnum.YEAR,
        offset=10,
        limit=5,
        viewer_id=viewer_id,
    )

    assert len(response.items) == 1
    assert response.items[0].result_type == "content"
    assert response.items[0].score == pytest.approx(-2.0)

    popular_call = next(call for call in repository.calls if call[0] == "search_popular_content")
    assert popular_call[1]["period"] == SearchPopularPeriodEnum.YEAR
    assert popular_call[1]["offset"] == 10
    assert popular_call[1]["limit"] == 5
    assert popular_call[1]["content_type"] == ContentTypeEnum.POST
