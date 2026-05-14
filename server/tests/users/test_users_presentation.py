import uuid

import pytest
from sqlalchemy.orm.attributes import NO_VALUE

from src.users.presentation import build_user_avatar_get, build_user_get


class _AttrState:
    def __init__(self, loaded_value) -> None:
        self.loaded_value = loaded_value


class _InspectionState:
    def __init__(self, attrs) -> None:
        self.attrs = attrs


class _UserWithLazyAvatar:
    user_id = uuid.uuid4()
    avatar_asset_id = uuid.uuid4()
    avatar_crop = {"x": 0.1, "y": 0.2, "size": 0.6}
    username = "alice"
    display_name = None
    bio = None
    links = []
    subscribers_count = 0
    is_admin = False

    @property
    def avatar_asset(self):
        raise AssertionError("avatar_asset relationship must not be lazy-loaded")


class _UserWithLazySubscribers(_UserWithLazyAvatar):
    avatar_asset_id = None
    avatar_crop = None

    @property
    def subscribers(self):
        raise AssertionError("subscribers relationship must not be lazy-loaded")


class _AvatarAssetWithLazyVariants:
    @property
    def variants(self):
        raise AssertionError("asset variants relationship must not be lazy-loaded")


@pytest.mark.asyncio
async def test_build_user_avatar_get_skips_unloaded_avatar_relationship(monkeypatch) -> None:
    user = _UserWithLazyAvatar()

    monkeypatch.setattr(
        "src.users.presentation.sa_inspect",
        lambda _instance: _InspectionState({"avatar_asset": _AttrState(NO_VALUE)}),
    )

    assert await build_user_avatar_get(user) is None


@pytest.mark.asyncio
async def test_build_user_avatar_get_skips_unloaded_avatar_variants(monkeypatch) -> None:
    user = _UserWithLazyAvatar()
    avatar_asset = _AvatarAssetWithLazyVariants()
    states = {
        id(user): _InspectionState({"avatar_asset": _AttrState(avatar_asset)}),
        id(avatar_asset): _InspectionState({"variants": _AttrState(NO_VALUE)}),
    }

    monkeypatch.setattr(
        "src.users.presentation.sa_inspect",
        lambda instance: states[id(instance)],
    )

    avatar = await build_user_avatar_get(user)

    assert avatar is not None
    assert avatar.small_url is None
    assert avatar.medium_url is None


@pytest.mark.asyncio
async def test_build_user_get_skips_unloaded_subscribers(monkeypatch) -> None:
    user = _UserWithLazySubscribers()

    monkeypatch.setattr(
        "src.users.presentation.sa_inspect",
        lambda _instance: _InspectionState({
            "avatar_asset": _AttrState(NO_VALUE),
            "subscribers": _AttrState(NO_VALUE),
        }),
    )

    result = await build_user_get(user, viewer_id=uuid.uuid4())

    assert result.is_subscribed is False
