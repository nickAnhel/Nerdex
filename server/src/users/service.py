import uuid

from sqlalchemy.exc import IntegrityError, NoResultFound

from src.assets.service import AssetService
from src.assets.storage import AssetStorage
from src.s3.exceptions import CantDeleteFileFromStorage
from src.users.enums import UserOrder
from src.users.presentation import build_user_get, build_user_get_many
from src.users.exceptions import (
    CantSubscribeToUser,
    CantUnsubscribeFromUser,
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
    UserUpdate,
)
from src.users.utils import get_password_hash

LEGACY_PROFILE_PHOTO_SMALL_PREFIX = "PPs@"
LEGACY_PROFILE_PHOTO_MEDIUM_PREFIX = "PPm@"
LEGACY_PROFILE_PHOTO_LARGE_PREFIX = "PPl@"


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        asset_service: AssetService,
        avatar_storage: AssetStorage,
    ) -> None:
        self._repository: UserRepository = repository
        self._asset_service = asset_service
        self._avatar_storage = avatar_storage

    async def create_user(
        self,
        data: UserCreate,
    ) -> UserGet:
        """Create new user."""

        user_data = data.model_dump()
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
        """Update current user."""

        try:
            user = await self._repository.update(
                data=data.model_dump(exclude_none=True),
                user_id=user_id,
            )
            return await build_user_get(user, storage=self._avatar_storage)

        except IntegrityError as exc:
            raise UsernameAlreadyExists(
                f"User with username {data.username} already exists"
            ) from exc

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
            await self._repository.subscribe(
                user_id=user_id, subscriber_id=subscriber_id
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
            await self._repository.unsubscribe(
                user_id=user_id, subscriber_id=subscriber_id
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
