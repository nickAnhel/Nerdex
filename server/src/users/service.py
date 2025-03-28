import uuid
from pathlib import Path

from sqlalchemy.exc import NoResultFound, IntegrityError

from src.users.repository import UserRepository
from src.users.enums import UserOrder
from src.users.utils import get_password_hash
from src.users.exceptions import (
    UserNotFound,
    UsernameOrEmailAlreadyExists,
)
from src.users.schemas import (
    UserCreate,
    UserUpdate,
    UserGet,
    UserGetWithPassword,
)


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
