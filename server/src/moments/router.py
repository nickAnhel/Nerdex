import uuid

from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_optional_user, get_current_user
from src.common.schemas import Status
from src.moments.dependencies import get_moment_service
from src.moments.enums import MomentOrder, MomentProfileFilter
from src.moments.schemas import MomentCreate, MomentEditorGet, MomentGet, MomentUpdate
from src.moments.service import MomentService
from src.users.schemas import UserGet


router = APIRouter(
    prefix="/moments",
    tags=["Moments"],
)


@router.post("/")
async def create_moment(
    data: MomentCreate,
    user: UserGet = Depends(get_current_user),
    moment_service: MomentService = Depends(get_moment_service),
) -> MomentGet:
    return await moment_service.create_moment(user=user, data=data)


@router.get("/list")
async def get_moments(
    order: MomentOrder = MomentOrder.PUBLISHED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user_id: uuid.UUID | None = None,
    profile_filter: MomentProfileFilter = MomentProfileFilter.PUBLIC,
    user: UserGet | None = Depends(get_current_optional_user),
    moment_service: MomentService = Depends(get_moment_service),
) -> list[MomentGet]:
    return await moment_service.get_moments(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
        user_id=user_id,
        user=user,
        profile_filter=profile_filter,
    )


@router.get("/feed")
async def get_moments_feed(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: UserGet | None = Depends(get_current_optional_user),
    moment_service: MomentService = Depends(get_moment_service),
) -> list[MomentGet]:
    return await moment_service.get_feed(user=user, offset=offset, limit=limit)


@router.get("/{moment_id}")
async def get_moment(
    moment_id: uuid.UUID,
    user: UserGet | None = Depends(get_current_optional_user),
    moment_service: MomentService = Depends(get_moment_service),
) -> MomentGet:
    return await moment_service.get_moment(moment_id=moment_id, user=user)


@router.get("/{moment_id}/editor")
async def get_moment_editor(
    moment_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    moment_service: MomentService = Depends(get_moment_service),
) -> MomentEditorGet:
    return await moment_service.get_moment_editor(moment_id=moment_id, user=user)


@router.put("/{moment_id}")
async def update_moment(
    moment_id: uuid.UUID,
    data: MomentUpdate,
    user: UserGet = Depends(get_current_user),
    moment_service: MomentService = Depends(get_moment_service),
) -> MomentGet:
    return await moment_service.update_moment(user=user, moment_id=moment_id, data=data)


@router.delete("/{moment_id}")
async def delete_moment(
    moment_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    moment_service: MomentService = Depends(get_moment_service),
) -> Status:
    await moment_service.delete_moment(user=user, moment_id=moment_id)
    return Status(detail="Moment deleted successfully")
