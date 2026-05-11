from fastapi import HTTPException, Request, status

from src.content.exceptions import ContentNotFound, InvalidContentAction


async def content_not_found_handler(request: Request, exc: ContentNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=exc.message,
    )


async def invalid_content_action_handler(request: Request, exc: InvalidContentAction) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.message,
    )
