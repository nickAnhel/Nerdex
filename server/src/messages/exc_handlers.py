from typing import NoReturn

from fastapi import HTTPException, status
from fastapi.requests import Request

from src.messages.exceptions import (
    CantDeleteMessage,
    CantReactToMessage,
    CantUpdateMessage,
    InvalidMessageAssets,
    InvalidMessageReply,
)


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


async def invalid_message_reply_handler(request: Request, exc: InvalidMessageReply) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


async def invalid_message_assets_handler(request: Request, exc: InvalidMessageAssets) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )


async def cant_react_to_message_handler(request: Request, exc: CantReactToMessage) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(exc),
    )
