from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status

from src.auth.dependencies import get_current_optional_user, get_current_user
from src.schemas import Status
from src.users.dependencies import get_user_service
from src.users.enums import UserOrder
from src.users.schemas import UserCreate, UserGet, UserUpdate
from src.users.service import UserService

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
    user: UserGet | None = Depends(get_current_optional_user),
    user_service: UserService = Depends(get_user_service),
) -> list[UserGet]:
    return await user_service.get_users(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
        curr_user=user,
    )


@router.get("/search")
async def search_users(
    query: Annotated[str, Query(max_length=50)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet | None = Depends(get_current_optional_user),
    user_service: UserService = Depends(get_user_service),
) -> list[UserGet]:
    return await user_service.search_users(
        query=query,
        offset=offset,
        limit=limit,
        curr_user=user,
    )


@router.get("/")
async def get_user_by_id(
    user_id: UUID,
    user: UserGet | None = Depends(get_current_optional_user),
    user_service: UserService = Depends(get_user_service),
) -> UserGet:
    return await user_service.get_user(user_id=user_id, curr_user=user)


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


@router.post("/subscribe")
async def subscribe_to_user(
    user_id: UUID,
    user: UserGet = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> Status:
    await user_service.subscribe(user_id=user_id, subscriber_id=user.user_id)
    return Status(detail="User subscribed successfully")


@router.delete("/unsubscribe")
async def unsubscribe_from_user(
    user_id: UUID,
    user: UserGet = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> Status:
    await user_service.unsubscribe(user_id=user_id, subscriber_id=user.user_id)
    return Status(detail="User unsubscribed successfully")


@router.get("/subscriptions")
async def get_subscriptions(
    user_id: UUID,
    offset: int = 0,
    limit: int = 100,
    user: UserGet | None = Depends(get_current_optional_user),
    user_service: UserService = Depends(get_user_service),
) -> list[UserGet]:
    return await user_service.get_subscriptions(
        curr_user=user,
        user_id=user_id,
        offset=offset,
        limit=limit,
    )


@router.put("/photo")
async def update_profile_photo(
    photo: UploadFile,
    user: UserGet = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> Status:
    if photo.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only jpeg or png files are allowed for profile photos",
        )

    await user_service.update_profile_photo(user_id=user.user_id, photo=photo.file)  # type: ignore
    return Status(detail="Profile photo updated successfully")


@router.delete("/photo")
async def delete_profile_photo(
    user: UserGet = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
) -> Status:
    await user_service.delete_profile_photo(user_id=user.user_id)
    return Status(detail="Profile photo deleted successfully")


@router.get("/{username}")
async def get_user_by_username(
    username: str,
    user: UserGet | None = Depends(get_current_optional_user),
    user_service: UserService = Depends(get_user_service),
) -> UserGet:
    return await user_service.get_user(username=username, curr_user=user)
