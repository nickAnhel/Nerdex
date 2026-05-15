from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.auth.dependencies import get_current_optional_user
from src.search.dependencies import get_search_service
from src.search.enums import SearchSortEnum, SearchTypeEnum
from src.search.schemas import SearchListGet
from src.search.service import SearchService
from src.users.schemas import UserGet

router = APIRouter(
    prefix="/search",
    tags=["Search"],
)


@router.get("")
async def search(
    q: Annotated[str, Query(min_length=1, max_length=120)],
    type: SearchTypeEnum = SearchTypeEnum.ALL,
    sort: SearchSortEnum = SearchSortEnum.RELEVANCE,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    user: UserGet | None = Depends(get_current_optional_user),
    search_service: SearchService = Depends(get_search_service),
) -> SearchListGet:
    return await search_service.search(
        query=q,
        search_type=type,
        sort=sort,
        offset=offset,
        limit=limit,
        viewer_id=user.user_id if user is not None else None,
    )
