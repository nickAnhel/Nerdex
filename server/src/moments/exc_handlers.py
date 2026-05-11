from fastapi import HTTPException, Request, status

from src.moments.exceptions import InvalidMoment, MomentNotFound


async def moment_not_found_handler(request: Request, exc: MomentNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=exc.message,
    )


async def invalid_moment_handler(request: Request, exc: InvalidMoment) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=exc.message,
    )
