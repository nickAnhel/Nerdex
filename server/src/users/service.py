from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, NoResultFound

from src.assets.service import AssetService
from src.assets.storage import AssetStorage
from src.auth.utils import validate_password
from src.s3.exceptions import CantDeleteFileFromStorage
from src.users.enums import UserOrder
from src.users.presentation import build_user_get, build_user_get_many
from src.users.exceptions import (
    CantSubscribeToUser,
    CantUnsubscribeFromUser,
    InvalidCurrentPassword,
    SamePassword,
    WeakPassword,
    UsernameAlreadyExists,
    UserNotFound,
    UserNotInSubscriptions,
)
from src.users.repository import UserRepository
from src.users.schemas import (
    UserCreate,
    UserGet,
    UserGetWithPassword,
    UserAvatarUpdate,
    UserPasswordUpdate,
    UserProfileUpdate,
    UserUpdate,
)
from src.users.utils import get_password_hash

if TYPE_CHECKING:
    from src.activity.service import ActivityService

LEGACY_PROFILE_PHOTO_SMALL_PREFIX = "PPs@"
LEGACY_PROFILE_PHOTO_MEDIUM_PREFIX = "PPm@"
LEGACY_PROFILE_PHOTO_LARGE_PREFIX = "PPl@"
PASSWORD_LETTER_RE = re.compile(r"[A-Za-z]")
PASSWORD_DIGIT_RE = re.compile(r"\d")


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        asset_service: AssetService,
        avatar_storage: AssetStorage,
        activity_service: ActivityService | None = None,
    ) -> None:
        self._repository: UserRepository = repository
        self._asset_service = asset_service
        self._avatar_storage = avatar_storage
        self._activity_service = activity_service

    async def create_user(
        self,
        data: UserCreate,
    ) -> UserGet:
        """Create new user."""

        user_data = data.model_dump()
        user_data["username"] = user_data["username"].strip()
        user_data["display_name"] = self._normalize_optional_text(user_data.get("display_name"))
        user_data["bio"] = self._normalize_optional_text(user_data.get("bio"))
        user_data["links"] = self._normalize_links(user_data.get("links") or [])
        user_data["hashed_password"] = get_password_hash(user_data["password"])
        del user_data["password"]

        try:
            user = await self._repository.create(user_data)
            return await build_user_get(user, storage=self._avatar_storage)
        except IntegrityError as exc:
            raise UsernameAlreadyExists(
                f"Username {data.username!r} already exists"
            ) from exc

    async def get_user(
        self,
        curr_user: UserGet | None = None,
        include_password: bool = False,
        **filters,
    ) -> UserGet | UserGetWithPassword:
        """Get user by filters (username or id)."""

        try:
            user = await self._repository.get_single(**filters)

        except NoResultFound as exc:
            raise UserNotFound(f"User with filters {filters!r} not found") from exc

        if include_password:
            return UserGetWithPassword.model_validate(user)

        return await build_user_get(
            user,
            viewer_id=curr_user.user_id if curr_user else None,
            storage=self._avatar_storage,
        )

    async def get_users(
        self,
        order: UserOrder,
        desc: bool,
        offset: int,
        limit: int,
        curr_user: UserGet | None = None,
    ) -> list[UserGet]:
        """Get users with pagination and sorting."""

        users = await self._repository.get_multi(
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )

        return await build_user_get_many(
            users,
            viewer_id=curr_user.user_id if curr_user else None,
            storage=self._avatar_storage,
        )

    async def search_users(
        self,
        query: str,
        offset: int,
        limit: int,
        curr_user: UserGet | None = None,
    ) -> list[UserGet]:
        """Search users with pagination and sorting."""

        users = await self._repository.search(
            search_query=query,
            offset=offset,
            limit=limit,
        )

        return await build_user_get_many(
            users,
            viewer_id=curr_user.user_id if curr_user else None,
            storage=self._avatar_storage,
        )

    async def update_user(
        self,
        user_id: uuid.UUID,
        data: UserUpdate,
    ) -> UserGet:
        return await self.update_profile(
            user_id=user_id,
            data=UserProfileUpdate.model_validate(data.model_dump(exclude_unset=True)),
        )

    async def update_profile(
        self,
        user_id: uuid.UUID,
        data: UserProfileUpdate,
    ) -> UserGet:
        """Update current user."""
        payload = data.model_dump(exclude_unset=True)
        if "username" in payload and payload["username"] is not None:
            payload["username"] = payload["username"].strip()
        if "display_name" in payload:
            payload["display_name"] = self._normalize_optional_text(payload["display_name"])
        if "bio" in payload:
            payload["bio"] = self._normalize_optional_text(payload["bio"])
        if "links" in payload:
            payload["links"] = self._normalize_links(payload["links"] or [])

        if not payload:
            current_user = await self._repository.get_single(user_id=user_id)
            return await build_user_get(current_user, storage=self._avatar_storage)

        try:
            user = await self._repository.update(
                data=payload,
                user_id=user_id,
            )
            return await build_user_get(user, storage=self._avatar_storage)

        except IntegrityError as exc:
            raise UsernameAlreadyExists(
                f"User with username {payload.get('username')!r} already exists"
            ) from exc

    async def change_password(
        self,
        *,
        user_id: uuid.UUID,
        data: UserPasswordUpdate,
    ) -> None:
        user = await self.get_user(
            user_id=user_id,
            include_password=True,
        )
        assert isinstance(user, UserGetWithPassword)

        if not validate_password(data.current_password, user.hashed_password):
            raise InvalidCurrentPassword("Current password is incorrect")
        if validate_password(data.new_password, user.hashed_password):
            raise SamePassword("New password must differ from current password")
        self._validate_new_password_strength(data.new_password)

        new_hash = get_password_hash(data.new_password)
        await self._repository.update_hashed_password(
            user_id=user_id,
            hashed_password=new_hash,
        )

    async def delete_user(
        self,
        user_id: uuid.UUID,
    ) -> None:
        """Delete user by id."""
        if not await self._delete_all_files_from_storage(user_id=user_id):
            raise CantDeleteFileFromStorage("Failed to delete file from S3")

        await self._repository.delete(user_id=user_id)

    async def subscribe(
        self,
        user_id: uuid.UUID,
        subscriber_id: uuid.UUID,
    ) -> None:
        """Subscribe to user."""

        if user_id == subscriber_id:
            raise CantSubscribeToUser("Can't subscribe to yourself")

        try:
            changed = await self._repository.subscribe(
                user_id=user_id, subscriber_id=subscriber_id
            )
            if changed and self._activity_service is not None:
                await self._activity_service.log_user_follow(
                    user_id=subscriber_id,
                    target_user_id=user_id,
                )
        except NoResultFound as exc:
            raise UserNotFound(f"User with id {user_id} not found") from exc

    async def unsubscribe(
        self,
        user_id: uuid.UUID,
        subscriber_id: uuid.UUID,
    ) -> None:
        """Unsubscribe from user."""

        if user_id == subscriber_id:
            raise CantUnsubscribeFromUser("Can't unsubscribe from yourself")

        try:
            changed = await self._repository.unsubscribe(
                user_id=user_id, subscriber_id=subscriber_id
            )
            if changed and self._activity_service is not None:
                await self._activity_service.log_user_unfollow(
                    user_id=subscriber_id,
                    target_user_id=user_id,
                )

        except NoResultFound as exc:
            raise UserNotFound(f"User with id {user_id} not found") from exc

        except ValueError as exc:
            raise UserNotInSubscriptions(
                f"User with id {subscriber_id} not found in subscribers of {user_id}"
            ) from exc

    async def get_subscriptions(
        self,
        user_id: uuid.UUID,
        curr_user: UserGet | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[UserGet]:
        """Get user subsctiptions."""

        try:
            users = await self._repository.get_subscriptions(user_id=user_id)
        except NoResultFound as exc:
            raise UserNotFound(f"User with id {user_id} not found") from exc

        users = users[offset : offset + limit]
        return await build_user_get_many(
            users,
            viewer_id=curr_user.user_id if curr_user else None,
            storage=self._avatar_storage,
        )

    async def _delete_all_files_from_storage(
        self,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete all user files from storage."""

        from src.s3.utils import delete_files

        return await delete_files(
            filenames=[
                LEGACY_PROFILE_PHOTO_SMALL_PREFIX + str(user_id),
                LEGACY_PROFILE_PHOTO_MEDIUM_PREFIX + str(user_id),
                LEGACY_PROFILE_PHOTO_LARGE_PREFIX + str(user_id),
            ],
        )

    async def update_avatar(
        self,
        user_id: uuid.UUID,
        data: UserAvatarUpdate,
    ) -> UserGet:
        """Update user avatar from an uploaded image asset."""

        current_user = await self._repository.get_single(user_id=user_id)
        previous_avatar_asset_id = current_user.avatar_asset_id

        await self._asset_service.generate_avatar_variants(
            asset_id=data.asset_id,
            owner_id=user_id,
            crop=data.crop.model_dump(),
        )

        user = await self._repository.set_avatar(
            user_id=user_id,
            avatar_asset_id=data.asset_id,
            avatar_crop=data.crop.model_dump(),
        )

        if previous_avatar_asset_id is not None and previous_avatar_asset_id != data.asset_id:
            await self._asset_service.mark_asset_orphaned_if_unreferenced(
                asset_id=previous_avatar_asset_id,
            )

        return await build_user_get(user, storage=self._avatar_storage)

    async def delete_avatar(
        self,
        user_id: uuid.UUID,
    ) -> UserGet:
        """Remove the current avatar selection."""

        current_user = await self._repository.get_single(user_id=user_id)
        previous_avatar_asset_id = current_user.avatar_asset_id
        user = await self._repository.clear_avatar(user_id=user_id)

        if previous_avatar_asset_id is not None:
            await self._asset_service.mark_asset_orphaned_if_unreferenced(
                asset_id=previous_avatar_asset_id,
            )

        return await build_user_get(user, storage=self._avatar_storage)

    def _normalize_optional_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _normalize_links(self, links: list[dict[str, object]]) -> list[dict[str, str]]:
        normalized_links: list[dict[str, str]] = []
        for link in links:
            label_value = link.get("label")
            url_value = link.get("url")
            label = str(label_value).strip() if label_value is not None else ""
            url = str(url_value).strip() if url_value is not None else ""
            if not label or not url:
                continue
            normalized_links.append(
                {
                    "label": label,
                    "url": url,
                }
            )
        return normalized_links

    def _validate_new_password_strength(self, password: str) -> None:
        if not PASSWORD_LETTER_RE.search(password) or not PASSWORD_DIGIT_RE.search(password):
            raise WeakPassword(
                "New password must contain at least one letter and one digit"
            )
