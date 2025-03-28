from uuid import UUID
from typing import Annotated
from fastapi import APIRouter, Depends, Query

from src.schemas import Status
from src.auth.dependencies import get_current_user

from src.users.dependencies import get_user_service
from src.users.service import UserService
from src.users.schemas import UserCreate, UserUpdate, UserGet
from src.users.enums import UserOrder


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post("/")
async def create_user(
    data: UserCreate,
    users_service: UserService = Depends(get_user_service),
) -> UserGet:
    return await users_service.create_user(data)


@router.get("/me")
async def get_current_user_info(
    user: UserGet = Depends(get_current_user),
) -> UserGet:
    return user


@router.get("/list")
async def get_users(
    order: UserOrder = UserOrder.ID,
    desc: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user_service: UserService = Depends(get_user_service),
) -> list[UserGet]:
    return await user_service.get_users(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
    )


@router.get("/search")
async def search_users(
    query: Annotated[str, Query(max_length=50)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user_service: UserService = Depends(get_user_service),
) -> list[UserGet]:
    return await user_service.search_users(
        query=query,
        offset=offset,
        limit=limit,
    )


@router.get("/")
async def get_user_by_id(
    user_id: UUID,
    user_service: UserService = Depends(get_user_service),
) -> UserGet:
    return await user_service.get_user(include_profile=True, user_id=user_id)


@router.put("/")
async def update_user(
    data: UserUpdate,
    user: UserGet = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> UserGet:
    return await user_service.update_user(user_id=user.user_id, data=data)


@router.delete("/")
async def delete_user(
    user: UserGet = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> Status:
    await user_service.delete_user(user_id=user.user_id)
    return Status(detail="User deleted successfully")
