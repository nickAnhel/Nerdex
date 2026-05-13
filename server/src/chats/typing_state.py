from __future__ import annotations

import uuid

import redis.asyncio as redis

from src.config import settings


TYPING_STATUS_EXPIRES_IN_SECONDS = 6

typing_redis = redis.from_url(
    settings.redis.socketio_manager_url,
    decode_responses=True,
)


def build_chat_typing_key(
    *,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
) -> str:
    return f"chats:typing:{chat_id}:{user_id}"


async def mark_chat_typing(
    *,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    username: str,
) -> None:
    await typing_redis.set(
        build_chat_typing_key(chat_id=chat_id, user_id=user_id),
        username,
        ex=TYPING_STATUS_EXPIRES_IN_SECONDS,
    )


async def clear_chat_typing(
    *,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    await typing_redis.delete(build_chat_typing_key(chat_id=chat_id, user_id=user_id))
