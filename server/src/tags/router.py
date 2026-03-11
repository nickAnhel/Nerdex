from fastapi import APIRouter, Depends, Query

from src.tags.dependencies import get_tag_service
from src.tags.schemas import TagGet
from src.tags.service import (
    DEFAULT_TAG_SUGGESTIONS_LIMIT,
    MAX_TAG_SUGGESTIONS_LIMIT,
    TagService,
)

router = APIRouter(
    prefix="/tags",
    tags=["Tags"],
)


@router.get("/suggestions")
async def get_tag_suggestions(
    query: str = Query(default=""),
    limit: int = Query(
        default=DEFAULT_TAG_SUGGESTIONS_LIMIT,
        ge=1,
        le=MAX_TAG_SUGGESTIONS_LIMIT,
    ),
    tag_service: TagService = Depends(get_tag_service),
) -> list[TagGet]:
    return await tag_service.suggest_tags(prefix=query, limit=limit)
