import uuid

from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_optional_user
from src.content.enums import ContentTypeEnum
from src.content.schemas import ContentListItemGet
from src.recommendations.dependencies import get_recommendation_service
from src.recommendations.schemas import (
    RecommendationFeedContentTypeEnum,
    RecommendationFeedSortEnum,
    SimilarContentListGet,
)
from src.recommendations.service import RecommendationService
from src.users.schemas import UserGet


router = APIRouter(
    prefix="/recommendations",
    tags=["Recommendations"],
)


@router.get("/feed")
async def get_recommendations_feed(
    content_type: RecommendationFeedContentTypeEnum = RecommendationFeedContentTypeEnum.ALL,
    sort: RecommendationFeedSortEnum = RecommendationFeedSortEnum.RELEVANCE,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: UserGet | None = Depends(get_current_optional_user),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
) -> list[ContentListItemGet]:
    return await recommendation_service.get_recommendations_feed(
        viewer_id=user.user_id if user is not None else None,
        content_type=content_type,
        sort=sort,
        offset=offset,
        limit=limit,
    )


@router.get("/content/{content_id}/similar")
async def get_similar_content(
    content_id: uuid.UUID,
    limit: int = Query(default=8, ge=1, le=50),
    content_type: ContentTypeEnum | None = None,
    user: UserGet | None = Depends(get_current_optional_user),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
) -> SimilarContentListGet:
    return await recommendation_service.get_similar_content(
        content_id=content_id,
        viewer_id=user.user_id if user is not None else None,
        limit=limit,
        content_type=content_type,
    )
