import uuid

from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_optional_user, get_current_user
from src.common.schemas import Status
from src.users.schemas import UserGet
from src.videos.dependencies import get_video_service
from src.videos.enums import VideoOrder, VideoProfileFilter
from src.videos.schemas import VideoCardGet, VideoCreate, VideoEditorGet, VideoGet, VideoRating, VideoUpdate
from src.videos.service import VideoService

router = APIRouter(
    prefix="/videos",
    tags=["Videos"],
)


@router.post("/")
async def create_video(
    data: VideoCreate,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoGet:
    return await video_service.create_video(user=user, data=data)


@router.get("/list")
async def get_videos(
    order: VideoOrder = VideoOrder.PUBLISHED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user_id: uuid.UUID | None = None,
    profile_filter: VideoProfileFilter = VideoProfileFilter.PUBLIC,
    user: UserGet | None = Depends(get_current_optional_user),
    video_service: VideoService = Depends(get_video_service),
) -> list[VideoCardGet]:
    return await video_service.get_videos(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
        user_id=user_id,
        user=user,
        profile_filter=profile_filter,
    )


@router.get("/{video_id}")
async def get_video(
    video_id: uuid.UUID,
    user: UserGet | None = Depends(get_current_optional_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoGet:
    return await video_service.get_video(video_id=video_id, user=user)


@router.get("/{video_id}/editor")
async def get_video_editor(
    video_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoEditorGet:
    return await video_service.get_video_editor(video_id=video_id, user=user)


@router.put("/{video_id}")
async def update_video(
    video_id: uuid.UUID,
    data: VideoUpdate,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoGet:
    return await video_service.update_video(user=user, video_id=video_id, data=data)


@router.delete("/{video_id}")
async def delete_video(
    video_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> Status:
    await video_service.delete_video(user=user, video_id=video_id)
    return Status(detail="Video deleted successfully")


@router.post("/{video_id}/like")
async def like_video(
    video_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoRating:
    return await video_service.add_like_to_video(video_id=video_id, user_id=user.user_id)


@router.delete("/{video_id}/like")
async def unlike_video(
    video_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoRating:
    return await video_service.remove_like_from_video(video_id=video_id, user_id=user.user_id)


@router.post("/{video_id}/dislike")
async def dislike_video(
    video_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoRating:
    return await video_service.add_dislike_to_video(video_id=video_id, user_id=user.user_id)


@router.delete("/{video_id}/dislike")
async def undislike_video(
    video_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    video_service: VideoService = Depends(get_video_service),
) -> VideoRating:
    return await video_service.remove_dislike_from_video(video_id=video_id, user_id=user.user_id)
