import uuid

from fastapi import APIRouter, Depends, Query

from src.articles.dependencies import get_article_service
from src.articles.enums import ArticleOrder, ArticleProfileFilter
from src.articles.schemas import ArticleCardGet, ArticleCreate, ArticleEditorGet, ArticleGet, ArticleRating, ArticleUpdate
from src.articles.service import ArticleService
from src.auth.dependencies import get_current_optional_user, get_current_user
from src.common.schemas import Status
from src.users.schemas import UserGet

router = APIRouter(
    prefix="/articles",
    tags=["Articles"],
)


@router.post("/")
async def create_article(
    data: ArticleCreate,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleGet:
    return await article_service.create_article(user=user, data=data)


@router.get("/list")
async def get_articles(
    order: ArticleOrder = ArticleOrder.PUBLISHED_AT,
    desc: bool = True,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=0, lt=1000),
    user_id: uuid.UUID | None = None,
    profile_filter: ArticleProfileFilter = ArticleProfileFilter.PUBLIC,
    user: UserGet | None = Depends(get_current_optional_user),
    article_service: ArticleService = Depends(get_article_service),
) -> list[ArticleCardGet]:
    return await article_service.get_articles(
        order=order,
        desc=desc,
        offset=offset,
        limit=limit,
        user=user,
        user_id=user_id,
        profile_filter=profile_filter,
    )


@router.get("/{article_id}")
async def get_article_by_id(
    article_id: uuid.UUID,
    user: UserGet | None = Depends(get_current_optional_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleGet:
    return await article_service.get_article(article_id=article_id, user=user)


@router.get("/{article_id}/editor")
async def get_article_editor(
    article_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleEditorGet:
    return await article_service.get_article_editor(article_id=article_id, user=user)


@router.put("/{article_id}")
async def update_article(
    article_id: uuid.UUID,
    data: ArticleUpdate,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleGet:
    return await article_service.update_article(
        user=user,
        data=data,
        article_id=article_id,
    )


@router.delete("/{article_id}")
async def delete_article(
    article_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> Status:
    await article_service.delete_article(user=user, article_id=article_id)
    return Status(detail="Article deleted successfully")


@router.post("/{article_id}/like")
async def like_article(
    article_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleRating:
    return await article_service.add_like_to_article(
        article_id=article_id,
        user_id=user.user_id,
    )


@router.delete("/{article_id}/like")
async def unlike_article(
    article_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleRating:
    return await article_service.remove_like_from_article(
        article_id=article_id,
        user_id=user.user_id,
    )


@router.post("/{article_id}/dislike")
async def dislike_article(
    article_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleRating:
    return await article_service.add_dislike_to_article(
        article_id=article_id,
        user_id=user.user_id,
    )


@router.delete("/{article_id}/dislike")
async def undislike_article(
    article_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    article_service: ArticleService = Depends(get_article_service),
) -> ArticleRating:
    return await article_service.remove_dislike_from_article(
        article_id=article_id,
        user_id=user.user_id,
    )
