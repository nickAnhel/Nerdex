import uuid

from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_optional_user, get_current_user
from src.comments.dependencies import get_comment_service
from src.comments.schemas import (
    DEFAULT_COMMENTS_LIMIT,
    MAX_COMMENTS_LIMIT,
    CommentCreate,
    CommentGet,
    CommentReactionGet,
    CommentUpdate,
    CommentsPageGet,
    RepliesPageGet,
)
from src.comments.service import CommentService
from src.common.schemas import Status
from src.users.schemas import UserGet

router = APIRouter(tags=["Comments"])


@router.get("/contents/{content_id}/comments")
async def get_root_comments(
    content_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_COMMENTS_LIMIT, ge=1, le=MAX_COMMENTS_LIMIT),
    user: UserGet | None = Depends(get_current_optional_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentsPageGet:
    return await comment_service.get_root_comments(
        content_id=content_id,
        offset=offset,
        limit=limit,
        user=user,
    )


@router.post("/contents/{content_id}/comments")
async def create_root_comment(
    content_id: uuid.UUID,
    data: CommentCreate,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentGet:
    return await comment_service.create_root_comment(
        content_id=content_id,
        user=user,
        data=data,
    )


@router.get("/comments/{comment_id}/replies")
async def get_replies(
    comment_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=DEFAULT_COMMENTS_LIMIT, ge=1, le=MAX_COMMENTS_LIMIT),
    user: UserGet | None = Depends(get_current_optional_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> RepliesPageGet:
    return await comment_service.get_replies(
        comment_id=comment_id,
        offset=offset,
        limit=limit,
        user=user,
    )


@router.post("/comments/{comment_id}/replies")
async def create_reply(
    comment_id: uuid.UUID,
    data: CommentCreate,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentGet:
    return await comment_service.create_reply(
        comment_id=comment_id,
        user=user,
        data=data,
    )


@router.patch("/comments/{comment_id}")
async def update_comment(
    comment_id: uuid.UUID,
    data: CommentUpdate,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentGet:
    return await comment_service.update_comment(
        comment_id=comment_id,
        user=user,
        data=data,
    )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> Status:
    await comment_service.delete_comment(
        comment_id=comment_id,
        user=user,
    )
    return Status(detail="Comment deleted successfully")


@router.post("/comments/{comment_id}/like")
async def like_comment(
    comment_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentReactionGet:
    return await comment_service.add_like(
        comment_id=comment_id,
        user_id=user.user_id,
    )


@router.delete("/comments/{comment_id}/like")
async def unlike_comment(
    comment_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentReactionGet:
    return await comment_service.remove_like(
        comment_id=comment_id,
        user_id=user.user_id,
    )


@router.post("/comments/{comment_id}/dislike")
async def dislike_comment(
    comment_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentReactionGet:
    return await comment_service.add_dislike(
        comment_id=comment_id,
        user_id=user.user_id,
    )


@router.delete("/comments/{comment_id}/dislike")
async def undislike_comment(
    comment_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    comment_service: CommentService = Depends(get_comment_service),
) -> CommentReactionGet:
    return await comment_service.remove_dislike(
        comment_id=comment_id,
        user_id=user.user_id,
    )
