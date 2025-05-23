import io
import uuid
from pathlib import Path

from PIL import Image
from sqlalchemy.exc import IntegrityError, NoResultFound

from src.config import settings
from src.s3.exceptions import CantDeleteFileFromStorage, CantUploadFileToStorage
from src.s3.utils import delete_files, upload_file
from src.users.enums import UserOrder
from src.users.exceptions import (
    CantSubscribeToUser,
    CantUnsubscribeFromUser,
    UsernameOrEmailAlreadyExists,
    UserNotFound,
    UserNotInSubscriptions,
)
from src.users.repository import UserRepository
from src.users.schemas import (
    UserCreate,
    UserGet,
    UserGetWithPassword,
    UserUpdate,
)
from src.users.utils import get_password_hash

BASE_DIR = Path(__file__).parent.parent.parent


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self._repository: UserRepository = repository

    async def create_user(
        self,
        data: UserCreate,
    ) -> UserGet:
        """Create new user."""

        user_data = data.model_dump()
        user_data["hashed_password"] = get_password_hash(user_data["password"])
        del user_data["password"]

        user = await self._repository.create(user_data)
        return UserGet.model_validate(user)

    async def get_user(
        self,
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

        return UserGet.model_validate(user)

    async def get_users(
        self,
        order: UserOrder,
        desc: bool,
        offset: int,
        limit: int,
    ) -> list[UserGet]:
        """Get users with pagination and sorting."""

        users = await self._repository.get_multi(
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )

        return [UserGet.model_validate(user) for user in users]

    async def search_users(
        self,
        query: str,
        offset: int,
        limit: int,
    ) -> list[UserGet]:
        """Search users with pagination and sorting."""

        users = await self._repository.search(
            search_query=query,
            offset=offset,
            limit=limit,
        )

        return [UserGet.model_validate(user) for user in users]

    async def update_user(
        self,
        user_id: uuid.UUID,
        data: UserUpdate,
    ) -> UserGet:
        """Update current user."""

        try:
            user = await self._repository.update(
                data=data.model_dump(),
                user_id=user_id,
            )
            return UserGet.model_validate(user)

        except IntegrityError as exc:
            raise UsernameOrEmailAlreadyExists(
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
        return [
            UserGet(
                user_id=user.user_id,
                username=user.username,
                subscribers_count=user.subscribers_count,
                is_admin=user.is_admin,
                is_subscribed=(
                    curr_user
                    and (curr_user.user_id in [u.user_id for u in user.subscribers])
                ),
            )
            for user in users
        ]

    async def _delete_all_files_from_storage(
        self,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete all user files from storage."""

        return await delete_files(
            filenames=[
                settings.file_prefixes.profile_photo_small + str(user_id),
                settings.file_prefixes.profile_photo_medium + str(user_id),
                settings.file_prefixes.profile_photo_large + str(user_id),
            ],
        )

    async def update_profile_photo(
        self,
        user_id: uuid.UUID,
        photo: bytes,
    ) -> bool:
        """Update user profile photo."""

        img_small = Image.open(photo)
        img_medium = Image.open(photo)
        img_large = Image.open(photo)

        img_small.thumbnail((80, 80))
        img_medium.thumbnail((160, 160))
        img_large.thumbnail((240, 240))

        img_small_bytes = io.BytesIO()
        img_medium_bytes = io.BytesIO()
        img_large_bytes = io.BytesIO()

        img_small.save(img_small_bytes, "PNG")
        img_small_bytes = img_small_bytes.getvalue()

        img_medium.save(img_medium_bytes, "PNG")
        img_medium_bytes = img_medium_bytes.getvalue()

        img_large.save(img_large_bytes, "PNG")
        img_large_bytes = img_large_bytes.getvalue()

        await self._delete_all_files_from_storage(user_id)

        if not (
            await upload_file(
                file=img_small_bytes,
                filename=settings.file_prefixes.profile_photo_small + str(user_id),
            )
            and await upload_file(
                file=img_medium_bytes,
                filename=settings.file_prefixes.profile_photo_medium + str(user_id),
            )
            and await upload_file(
                file=img_large_bytes,
                filename=settings.file_prefixes.profile_photo_large + str(user_id),
            )
        ):
            await self._delete_all_files_from_storage(user_id)
            raise CantUploadFileToStorage()

        return True

    async def delete_profile_photo(
        self,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete user profile photo."""

        if not await self._delete_all_files_from_storage(user_id):
            raise CantDeleteFileFromStorage()

        return True
