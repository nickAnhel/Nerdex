import uuid

from fastapi import APIRouter, Body, Depends, Query

from src.auth.dependencies import get_current_optional_user, get_current_user
from src.content.dependencies import get_content_service
from src.content.enums_list import ContentOrder
from src.content.enums import ContentProfileFilterEnum, ContentTypeEnum
from src.content.schemas import (
    ContentGalleryItemGet,
    ContentHistoryItemGet,
    ContentListItemGet,
    ContentReactionGet,
    ContentReactionWrite,
    ContentViewSessionGet,
    ContentViewSessionHeartbeat,
    ContentViewSessionStart,
)
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


@router.get("/publications")
async def get_author_publications(
    author_id: uuid.UUID,
    content_type: ContentTypeEnum | None = None,
    profile_filter: ContentProfileFilterEnum = ContentProfileFilterEnum.PUBLIC,
    order: ContentOrder = ContentOrder.PUBLISHED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet | None = Depends(get_current_optional_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentListItemGet]:
    viewer_id = user.user_id if user is not None else None
    return await content_service.get_publications(
        author_id=author_id,
        viewer_id=viewer_id,
        content_type=content_type,
        profile_filter=profile_filter,
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
    )


@router.get("/gallery")
async def get_author_gallery(
    author_id: uuid.UUID,
    profile_filter: ContentProfileFilterEnum = ContentProfileFilterEnum.PUBLIC,
    order: ContentOrder = ContentOrder.CREATED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet | None = Depends(get_current_optional_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentGalleryItemGet]:
    viewer_id = user.user_id if user is not None else None
    return await content_service.get_gallery(
        author_id=author_id,
        viewer_id=viewer_id,
        profile_filter=profile_filter,
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
    )


@router.get("/subscriptions")
async def get_subscriptions_feed(
    content_type: ContentTypeEnum | None = None,
    order: ContentOrder = ContentOrder.CREATED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentListItemGet]:
    return await content_service.get_subscriptions_feed(
        user_id=user.user_id,
        content_type=content_type,
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
    )


@router.get("/videos/recommendations")
async def get_video_recommendations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet | None = Depends(get_current_optional_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentListItemGet]:
    return await content_service.get_video_recommendations(
        viewer_id=user.user_id if user else None,
        offset=offset,
        limit=limit,
    )


@router.get("/videos/subscriptions")
async def get_video_subscriptions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentListItemGet]:
    return await content_service.get_video_subscriptions(
        user_id=user.user_id,
        offset=offset,
        limit=limit,
    )


@router.get("/history")
async def get_content_history(
    content_type: ContentTypeEnum | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> list[ContentHistoryItemGet]:
    return await content_service.get_history(
        user=user,
        content_type=content_type,
        offset=offset,
        limit=limit,
    )


@router.post("/{content_id}/reaction")
async def set_content_reaction(
    content_id: uuid.UUID,
    data: ContentReactionWrite,
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> ContentReactionGet:
    return await content_service.set_reaction(
        content_id=content_id,
        user=user,
        reaction_type=data.reaction_type,
    )


@router.delete("/{content_id}/reaction")
async def remove_content_reaction(
    content_id: uuid.UUID,
    data: ContentReactionWrite | None = Body(default=None),
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> ContentReactionGet:
    return await content_service.remove_reaction(
        content_id=content_id,
        user=user,
        reaction_type=data.reaction_type if data is not None else None,
    )


@router.post("/{content_id}/view-session/start")
async def start_content_view_session(
    content_id: uuid.UUID,
    data: ContentViewSessionStart,
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> ContentViewSessionGet:
    return await content_service.start_view_session(
        content_id=content_id,
        user=user,
        data=data,
    )


@router.post("/{content_id}/view-session/{session_id}/heartbeat")
async def heartbeat_content_view_session(
    content_id: uuid.UUID,
    session_id: uuid.UUID,
    data: ContentViewSessionHeartbeat,
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> ContentViewSessionGet:
    return await content_service.heartbeat_view_session(
        content_id=content_id,
        session_id=session_id,
        user=user,
        data=data,
    )


@router.post("/{content_id}/view-session/{session_id}/finish")
async def finish_content_view_session(
    content_id: uuid.UUID,
    session_id: uuid.UUID,
    data: ContentViewSessionHeartbeat,
    user: UserGet = Depends(get_current_user),
    content_service: ContentService = Depends(get_content_service),
) -> ContentViewSessionGet:
    return await content_service.finish_view_session(
        content_id=content_id,
        session_id=session_id,
        user=user,
        data=data,
    )
