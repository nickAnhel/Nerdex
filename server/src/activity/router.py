from fastapi import APIRouter, Depends, Query

from src.activity.dependencies import get_activity_service
from src.activity.enums import ActivityActionTypeEnum, ActivityPeriodEnum
from src.activity.schemas import ActivityEventListGet
from src.activity.service import ActivityService
from src.auth.dependencies import get_current_user
from src.content.enums import ContentTypeEnum
from src.users.schemas import UserGet


router = APIRouter(
    prefix="/activity",
    tags=["Activity"],
)


@router.get("")
async def get_my_activity(
    action_type: list[ActivityActionTypeEnum] | None = Query(default=None),
    content_type: ContentTypeEnum | None = None,
    period: ActivityPeriodEnum = ActivityPeriodEnum.ALL_TIME,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: UserGet = Depends(get_current_user),
    activity_service: ActivityService = Depends(get_activity_service),
) -> ActivityEventListGet:
    return await activity_service.get_my_activity(
        user_id=user.user_id,
        action_types=action_type,
        content_type=content_type,
        period=period,
        offset=offset,
        limit=limit,
    )
