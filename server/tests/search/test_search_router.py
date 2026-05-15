import uuid

import pytest

from src.auth.dependencies import get_current_optional_user
from src.search.enums import SearchSortEnum, SearchTypeEnum
from src.search.router import router, search
from src.search.schemas import SearchListGet
from src.users.schemas import UserGet


class FakeSearchService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def search(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return SearchListGet(items=[], offset=kwargs["offset"], limit=kwargs["limit"], has_more=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_search_route_uses_optional_user_dependency() -> None:
    route = next(route for route in router.routes if getattr(route, "path", None) == "/search")
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}

    assert get_current_optional_user in dependency_calls


@pytest.mark.anyio
async def test_search_endpoint_passes_params_to_service() -> None:
    viewer = UserGet(
        user_id=uuid.uuid4(),
        username="viewer",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
    )
    service = FakeSearchService()

    response = await search(
        q="full text",
        type=SearchTypeEnum.ARTICLE,
        sort=SearchSortEnum.OLDEST,
        offset=15,
        limit=7,
        user=viewer,
        search_service=service,  # type: ignore[arg-type]
    )

    assert response.offset == 15
    assert response.limit == 7
    assert response.has_more is False

    call = service.calls[0]
    assert call["query"] == "full text"
    assert call["search_type"] == SearchTypeEnum.ARTICLE
    assert call["sort"] == SearchSortEnum.OLDEST
    assert call["offset"] == 15
    assert call["limit"] == 7
    assert call["viewer_id"] == viewer.user_id
