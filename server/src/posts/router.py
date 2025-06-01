import uuid

from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_optional_user, get_current_user
from src.posts.dependencies import get_post_service
from src.posts.enums import PostOrder
from src.posts.schemas import PostCreate, PostGet, PostRating, PostUpdate
from src.posts.service import PostService
from src.schemas import Status
from src.users.schemas import UserGet

router = APIRouter(
    prefix="/posts",
    tags=["Posts"],
)


@router.post("/")
async def create_post(
    data: PostCreate,
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> PostGet:
    return await post_service.create_post(user, data)


@router.get("/list")
async def get_posts(
    order: PostOrder = PostOrder.ID,
    desc: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user_id: uuid.UUID | None = None,
    user: UserGet | None = Depends(get_current_optional_user),
    post_service: PostService = Depends(get_post_service),
) -> list[PostGet]:
    print(user)
    return await post_service.get_posts(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
        user=user,
        user_id=user_id,
    )


@router.get("/search", deprecated=True, description="In work")
async def search_posts():
    pass


@router.get("/")
async def get_post_by_id(
    post_id: uuid.UUID,
    post_service: PostService = Depends(get_post_service),
) -> PostGet:
    return await post_service.get_post(post_id)


@router.put("/")
async def update_post(
    post_id: uuid.UUID,
    data: PostUpdate,
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> PostGet:
    return await post_service.update_post(
        user=user,
        data=data,
        post_id=post_id,
    )


@router.delete("/")
async def delete_post(
    post_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> Status:
    await post_service.delete_post(user=user, post_id=post_id)
    return Status(detail="Post deleted successfully")


@router.post("/like")
async def like_post(
    post_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> PostRating:
    return await post_service.add_like_to_post(
        post_id=post_id,
        user_id=user.user_id,
    )


@router.post("/dislike")
async def dislike_post(
    post_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> PostRating:
    return await post_service.add_dislike_to_post(
        post_id=post_id,
        user_id=user.user_id,
    )


@router.delete("/like")
async def unlike_post(
    post_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> PostRating:
    return await post_service.remove_like_from_post(
        post_id=post_id,
        user_id=user.user_id,
    )


@router.delete("/dislike")
async def undislike_post(
    post_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> PostRating:
    return await post_service.remove_dislike_from_post(
        post_id=post_id,
        user_id=user.user_id,
    )


@router.get("/subscriptions")
async def get_subscriptions_posts(
    order: PostOrder = PostOrder.ID,
    desc: bool = False,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user: UserGet = Depends(get_current_user),
    post_service: PostService = Depends(get_post_service),
) -> list[PostGet]:
    return await post_service.get_user_subscriptions_posts(
        user_id=user.user_id,
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
    )
