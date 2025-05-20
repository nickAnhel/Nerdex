from typing import NoReturn

from fastapi import HTTPException, status
from fastapi.requests import Request

from src.messages.exceptions import CantDeleteMessage, CantUpdateMessage


async def cant_update_message_handler(request: Request, exc: CantUpdateMessage) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=str(exc),
    )


async def cant_delete_message_handler(request: Request, exc: CantDeleteMessage) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )
