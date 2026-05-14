import datetime
import uuid
from dataclasses import dataclass, field

import pytest

from src.auth.utils import validate_password
from src.assets.enums import AssetAccessTypeEnum, AssetStatusEnum, AssetTypeEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.users.exceptions import InvalidCurrentPassword, SamePassword, WeakPassword
from src.users.schemas import UserAvatarUpdate, UserPasswordUpdate, UserProfileUpdate
from src.users.service import UserService
from src.users.utils import get_password_hash


@dataclass
class FakeVariant:
    asset_variant_type: AssetVariantTypeEnum
    storage_bucket: str
    storage_key: str
    status: AssetVariantStatusEnum = AssetVariantStatusEnum.READY
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


@dataclass
class FakeAsset:
    asset_id: uuid.UUID
    owner_id: uuid.UUID
    asset_type: AssetTypeEnum
    status: AssetStatusEnum
    access_type: AssetAccessTypeEnum = AssetAccessTypeEnum.PRIVATE
    variants: list[FakeVariant] = field(default_factory=list)


@dataclass
class FakeUser:
    user_id: uuid.UUID
    username: str
    hashed_password: str
    display_name: str | None = None
    bio: str | None = None
    links: list[dict[str, str]] = field(default_factory=list)
    avatar_asset_id: uuid.UUID | None = None
    avatar_crop: dict[str, float] | None = None
    subscribers_count: int = 0
    is_admin: bool = False
    subscribers: list["FakeUser"] = field(default_factory=list)
    subscribed: list["FakeUser"] = field(default_factory=list)
    avatar_asset: FakeAsset | None = None


class FakeUserRepository:
    def __init__(self, user: FakeUser, assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.user = user
        self.assets = assets

    async def get_single(self, **filters) -> FakeUser:  # type: ignore[no-untyped-def]
        return self.user

    async def set_avatar(self, *, user_id: uuid.UUID, avatar_asset_id: uuid.UUID, avatar_crop: dict[str, float]) -> FakeUser:
        self.user.avatar_asset_id = avatar_asset_id
        self.user.avatar_crop = avatar_crop
        self.user.avatar_asset = self.assets[avatar_asset_id]
        return self.user

    async def clear_avatar(self, *, user_id: uuid.UUID) -> FakeUser:
        self.user.avatar_asset_id = None
        self.user.avatar_crop = None
        self.user.avatar_asset = None
        return self.user

    async def update(self, data: dict, **filters) -> FakeUser:  # type: ignore[no-untyped-def]
        for key, value in data.items():
            setattr(self.user, key, value)
        return self.user

    async def update_hashed_password(self, *, user_id: uuid.UUID, hashed_password: str) -> FakeUser:
        self.user.hashed_password = hashed_password
        return self.user


class FakeAssetService:
    def __init__(self) -> None:
        self.generated: list[tuple[uuid.UUID, uuid.UUID, dict[str, float]]] = []
        self.orphaned: list[uuid.UUID] = []

    async def generate_avatar_variants(self, *, asset_id: uuid.UUID, owner_id: uuid.UUID, crop: dict[str, float]) -> None:
        self.generated.append((asset_id, owner_id, crop))

    async def mark_asset_orphaned_if_unreferenced(self, *, asset_id: uuid.UUID) -> bool:
        self.orphaned.append(asset_id)
        return True


class FakeAvatarStorage:
    async def generate_presigned_get(
        self,
        *,
        bucket: str,
        key: str,
        download_filename: str | None = None,
        inline: bool = True,
        response_content_type: str | None = None,
    ) -> str:
        return f"https://download.test/{bucket}/{key}"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def build_asset(asset_id: uuid.UUID, owner_id: uuid.UUID) -> FakeAsset:
    return FakeAsset(
        asset_id=asset_id,
        owner_id=owner_id,
        asset_type=AssetTypeEnum.IMAGE,
        status=AssetStatusEnum.READY,
        variants=[
            FakeVariant(
                asset_variant_type=AssetVariantTypeEnum.AVATAR_SMALL,
                storage_bucket="bucket",
                storage_key=f"{asset_id}/avatar_small.webp",
            ),
            FakeVariant(
                asset_variant_type=AssetVariantTypeEnum.AVATAR_MEDIUM,
                storage_bucket="bucket",
                storage_key=f"{asset_id}/avatar_medium.webp",
            ),
        ],
    )


@pytest.mark.anyio
async def test_update_avatar_sets_crop_and_returns_avatar_urls() -> None:
    user_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    asset = build_asset(asset_id, user_id)
    user = FakeUser(
        user_id=user_id,
        username="tester",
        hashed_password="hashed",
    )
    repository = FakeUserRepository(user=user, assets={asset_id: asset})
    asset_service = FakeAssetService()
    service = UserService(
        repository=repository,  # type: ignore[arg-type]
        asset_service=asset_service,  # type: ignore[arg-type]
        avatar_storage=FakeAvatarStorage(),  # type: ignore[arg-type]
    )

    response = await service.update_avatar(
        user_id=user_id,
        data=UserAvatarUpdate.model_validate(
            {
                "asset_id": str(asset_id),
                "crop": {"x": 0.18, "y": 0.07, "size": 0.62},
            }
        ),
    )

    assert response.avatar_asset_id == asset_id
    assert response.avatar is not None
    assert response.avatar.crop.size == 0.62
    assert response.avatar.small_url == f"https://download.test/bucket/{asset_id}/avatar_small.webp"
    assert response.avatar.medium_url == f"https://download.test/bucket/{asset_id}/avatar_medium.webp"
    assert asset_service.generated == [
        (asset_id, user_id, {"x": 0.18, "y": 0.07, "size": 0.62})
    ]


@pytest.mark.anyio
async def test_delete_avatar_clears_avatar_fields() -> None:
    user_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    asset = build_asset(asset_id, user_id)
    user = FakeUser(
        user_id=user_id,
        username="tester",
        hashed_password="hashed",
        avatar_asset_id=asset_id,
        avatar_crop={"x": 0.2, "y": 0.1, "size": 0.6},
        avatar_asset=asset,
    )
    repository = FakeUserRepository(user=user, assets={asset_id: asset})
    asset_service = FakeAssetService()
    service = UserService(
        repository=repository,  # type: ignore[arg-type]
        asset_service=asset_service,  # type: ignore[arg-type]
        avatar_storage=FakeAvatarStorage(),  # type: ignore[arg-type]
    )

    response = await service.delete_avatar(user_id=user_id)

    assert response.avatar_asset_id is None
    assert response.avatar is None
    assert asset_service.orphaned == [asset_id]


@pytest.mark.anyio
async def test_update_profile_normalizes_display_name_bio_and_links() -> None:
    user_id = uuid.uuid4()
    user = FakeUser(
        user_id=user_id,
        username="tester",
        hashed_password=get_password_hash("oldpass123"),
    )
    repository = FakeUserRepository(user=user, assets={})
    service = UserService(
        repository=repository,  # type: ignore[arg-type]
        asset_service=FakeAssetService(),  # type: ignore[arg-type]
        avatar_storage=FakeAvatarStorage(),  # type: ignore[arg-type]
    )

    response = await service.update_profile(
        user_id=user_id,
        data=UserProfileUpdate.model_validate(
            {
                "display_name": "   ",
                "bio": "   short bio   ",
                "links": [
                    {"label": " GitHub ", "url": "https://github.com/tester "},
                ],
            }
        ),
    )

    assert repository.user.display_name is None
    assert repository.user.bio == "short bio"
    assert repository.user.links == [{"label": "GitHub", "url": "https://github.com/tester"}]
    assert response.display_name == "tester"


@pytest.mark.anyio
async def test_change_password_successfully_updates_hash() -> None:
    user_id = uuid.uuid4()
    user = FakeUser(
        user_id=user_id,
        username="tester",
        hashed_password=get_password_hash("oldpass123"),
    )
    repository = FakeUserRepository(user=user, assets={})
    service = UserService(
        repository=repository,  # type: ignore[arg-type]
        asset_service=FakeAssetService(),  # type: ignore[arg-type]
        avatar_storage=FakeAvatarStorage(),  # type: ignore[arg-type]
    )

    await service.change_password(
        user_id=user_id,
        data=UserPasswordUpdate(
            current_password="oldpass123",
            new_password="newpass456",
        ),
    )

    assert validate_password("newpass456", repository.user.hashed_password)


@pytest.mark.anyio
async def test_change_password_rejects_invalid_current_password() -> None:
    user_id = uuid.uuid4()
    user = FakeUser(
        user_id=user_id,
        username="tester",
        hashed_password=get_password_hash("oldpass123"),
    )
    repository = FakeUserRepository(user=user, assets={})
    service = UserService(
        repository=repository,  # type: ignore[arg-type]
        asset_service=FakeAssetService(),  # type: ignore[arg-type]
        avatar_storage=FakeAvatarStorage(),  # type: ignore[arg-type]
    )

    with pytest.raises(InvalidCurrentPassword):
        await service.change_password(
            user_id=user_id,
            data=UserPasswordUpdate(
                current_password="wrongpass000",
                new_password="newpass456",
            ),
        )


@pytest.mark.anyio
async def test_change_password_rejects_same_or_weak_new_password() -> None:
    user_id = uuid.uuid4()
    user = FakeUser(
        user_id=user_id,
        username="tester",
        hashed_password=get_password_hash("oldpass123"),
    )
    repository = FakeUserRepository(user=user, assets={})
    service = UserService(
        repository=repository,  # type: ignore[arg-type]
        asset_service=FakeAssetService(),  # type: ignore[arg-type]
        avatar_storage=FakeAvatarStorage(),  # type: ignore[arg-type]
    )

    with pytest.raises(SamePassword):
        await service.change_password(
            user_id=user_id,
            data=UserPasswordUpdate(
                current_password="oldpass123",
                new_password="oldpass123",
            ),
        )

    with pytest.raises(WeakPassword):
        await service.change_password(
            user_id=user_id,
            data=UserPasswordUpdate(
                current_password="oldpass123",
                new_password="weakpass",
            ),
        )
