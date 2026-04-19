from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_optional_user, get_current_user
from src.content.dependencies import get_content_service
from src.content.enums_list import ContentOrder
from src.content.schemas import ContentListItemGet
from src.content.service import ContentService
from src.users.schemas import UserGet

router = APIRouter(
    prefix="/contents",
    tags=["Content"],
)


@router.get("/list")
async def get_feed(
    order: ContentOrder = ContentOrder.CREATED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet | None = Depends(get_current_optional_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentListItemGet]:
    viewer_id = user.user_id if user is not None else None
    return await content_service.get_feed(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
        viewer_id=viewer_id,
    )


@router.get("/subscriptions")
async def get_subscriptions_feed(
    order: ContentOrder = ContentOrder.CREATED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentListItemGet]:
    return await content_service.get_subscriptions_feed(
        user_id=user.user_id,
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
    )
