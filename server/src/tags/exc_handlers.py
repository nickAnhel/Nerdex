from fastapi import HTTPException, status
from fastapi.requests import Request

from src.tags.exceptions import InvalidTag


async def invalid_tag_handler(request: Request, exc: InvalidTag) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc),
    )
