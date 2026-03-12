from fastapi import HTTPException, status
from fastapi.requests import Request

from src.comments.exceptions import CommentNotFound, InvalidComment


async def comment_not_found_handler(request: Request, exc: CommentNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


async def invalid_comment_handler(request: Request, exc: InvalidComment) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )
