from fastapi import HTTPException, status
from fastapi.requests import Request

from src.posts.exceptions import PostNotFound, PostAlreadyRated


async def post_not_found_handler(request: Request, exc: PostNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


async def post_already_rated_handler(request: Request, exc: PostAlreadyRated) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )
