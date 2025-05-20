import uuid
from pathlib import Path

from sqlalchemy.exc import IntegrityError, NoResultFound

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
            raise UsernameOrEmailAlreadyExists(f"User with username {data.username} already exists") from exc

    async def delete_user(
        self,
        user_id: uuid.UUID,
    ) -> None:
        """Delete user by id."""

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
            await self._repository.subscribe(user_id=user_id, subscriber_id=subscriber_id)
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
            await self._repository.unsubscribe(user_id=user_id, subscriber_id=subscriber_id)

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
                is_subscribed=(curr_user and (curr_user.user_id in [u.user_id for u in user.subscribers])),
            )
            for user in users
        ]
