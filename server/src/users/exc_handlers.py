from fastapi import HTTPException, status
from fastapi.requests import Request


from src.users.exceptions import (
    UserNotFound,
    UsernameOrEmailAlreadyExists,
)


async def user_not_found_handler(request: Request, exc: UserNotFound) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


async def username_or_email_already_exists_handler(
    request: Request, exc: UsernameOrEmailAlreadyExists
) -> HTTPException:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=str(exc),
    )
