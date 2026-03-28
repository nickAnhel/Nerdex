from fastapi import HTTPException, status
from fastapi.requests import Request

from src.posts.exceptions import InvalidPost, PostNotFound


async def post_not_found_handler(request: Request, exc: PostNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


async def invalid_post_handler(request: Request, exc: InvalidPost) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )
