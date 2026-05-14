import uuid

import pytest

from src.activity.enums import ActivityActionTypeEnum, ActivityPeriodEnum
from src.activity.router import get_my_activity, router
from src.activity.schemas import ActivityEventListGet
from src.auth.dependencies import get_current_user
from src.content.enums import ContentTypeEnum
from src.users.schemas import UserGet


class FakeActivityService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def get_my_activity(self, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append(kwargs)
        return ActivityEventListGet(items=[], offset=kwargs["offset"], limit=kwargs["limit"], has_more=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_activity_route_requires_current_user_dependency() -> None:
    route = next(route for route in router.routes if getattr(route, "path", None) == "/activity")
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}

    assert get_current_user in dependency_calls


@pytest.mark.anyio
async def test_activity_endpoint_passes_filters_to_service() -> None:
    service = FakeActivityService()
    user = UserGet(
        user_id=uuid.uuid4(),
        username="viewer",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
    )

    response = await get_my_activity(
        action_type=[
            ActivityActionTypeEnum.USER_FOLLOW,
            ActivityActionTypeEnum.USER_UNFOLLOW,
        ],
        content_type=ContentTypeEnum.POST,
        period=ActivityPeriodEnum.MONTH,
        offset=20,
        limit=10,
        user=user,
        activity_service=service,  # type: ignore[arg-type]
    )

    call = service.calls[0]
    assert response.has_more is False
    assert call["user_id"] == user.user_id
    assert call["action_types"] == [
        ActivityActionTypeEnum.USER_FOLLOW,
        ActivityActionTypeEnum.USER_UNFOLLOW,
    ]
    assert call["content_type"] == ContentTypeEnum.POST
    assert call["period"] == ActivityPeriodEnum.MONTH
    assert call["offset"] == 20
    assert call["limit"] == 10
