from __future__ import annotations

import typing as tp
import uuid

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import NoInspectionAvailable
from sqlalchemy.orm.attributes import NO_VALUE

from src.assets.enums import AssetVariantStatusEnum, AssetVariantTypeEnum
from src.assets.storage import AssetStorage
from src.config import settings
from src.users.schemas import UserAvatarCrop, UserAvatarGet, UserGet


_avatar_storage: AssetStorage | None = None


def get_avatar_storage() -> AssetStorage:
    global _avatar_storage
    if _avatar_storage is None:
        _avatar_storage = AssetStorage(settings.storage)
    return _avatar_storage


async def build_user_get(
    user: tp.Any,
    *,
    viewer_id: uuid.UUID | None = None,
    storage: AssetStorage | None = None,
) -> UserGet:
    return UserGet(
        user_id=user.user_id,
        avatar_asset_id=user.avatar_asset_id,
        avatar=await build_user_avatar_get(user, storage=storage),
        username=user.username,
        subscribers_count=user.subscribers_count,
        is_admin=user.is_admin,
        is_subscribed=(
            viewer_id is not None
            and viewer_id in [
                subscriber.user_id
                for subscriber in _loaded_relationship_or_default(user, "subscribers", [])
            ]
        ),
    )


async def build_user_get_many(
    users: list[tp.Any],
    *,
    viewer_id: uuid.UUID | None = None,
    storage: AssetStorage | None = None,
) -> list[UserGet]:
    return [
        await build_user_get(user, viewer_id=viewer_id, storage=storage)
        for user in users
    ]


async def build_user_avatar_get(
    user: tp.Any,
    *,
    storage: AssetStorage | None = None,
) -> UserAvatarGet | None:
    if getattr(user, "avatar_asset_id", None) is None or getattr(user, "avatar_crop", None) is None:
        return None

    avatar_asset = _loaded_relationship_or_default(user, "avatar_asset", None)
    if avatar_asset is None:
        return None

    crop = UserAvatarCrop.model_validate(user.avatar_crop)
    storage = storage or get_avatar_storage()
    small_url = None
    medium_url = None

    for variant in _loaded_relationship_or_default(avatar_asset, "variants", []):
        if variant.status != AssetVariantStatusEnum.READY:
            continue
        if variant.asset_variant_type == AssetVariantTypeEnum.AVATAR_SMALL:
            small_url = await storage.generate_presigned_get(
                bucket=variant.storage_bucket,
                key=variant.storage_key,
            )
        elif variant.asset_variant_type == AssetVariantTypeEnum.AVATAR_MEDIUM:
            medium_url = await storage.generate_presigned_get(
                bucket=variant.storage_bucket,
                key=variant.storage_key,
            )

    return UserAvatarGet(
        small_url=small_url,
        medium_url=medium_url,
        crop=crop,
    )


def _loaded_relationship_or_default(
    instance: tp.Any,
    name: str,
    default: tp.Any,
) -> tp.Any:
    try:
        state = sa_inspect(instance)
    except NoInspectionAvailable:
        return getattr(instance, name, default)

    try:
        loaded_value = state.attrs[name].loaded_value
    except KeyError:
        return getattr(instance, name, default)

    if loaded_value is NO_VALUE:
        return default
    return loaded_value
