import uuid

from fastapi import APIRouter, Depends, Query

from src.schemas import Status
from src.users.schemas import UserGet
from src.auth.dependencies import get_current_user
from src.posts.dependencies import get_post_service
from src.posts.enums import PostOrder
from src.posts.schemas import PostCreate, PostGet, PostUpdate
from src.posts.service import PostService


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
    post_service: PostService = Depends(get_post_service),
) -> list[PostGet]:
    return await post_service.get_posts(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
    )


@router.get("/search")
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
