from __future__ import annotations

import typing as tp
import uuid

from src.events.schemas import EventGetWithUsers
from src.users.presentation import build_user_get

if tp.TYPE_CHECKING:
    from src.assets.storage import AssetStorage


async def build_event_get_with_users(
    event: tp.Any,
    *,
    storage: AssetStorage | None = None,
    viewer_id: uuid.UUID | None = None,
) -> EventGetWithUsers:
    altered_user = getattr(event, "altered_user", None)

    return EventGetWithUsers(
        event_id=event.event_id,
        chat_id=event.chat_id,
        user_id=event.user_id,
        event_type=event.event_type,
        altered_user_id=event.altered_user_id,
        created_at=event.created_at,
        chat_seq=getattr(event, "chat_seq", None),
        user=await build_user_get(
            event.user,
            storage=storage,
            viewer_id=viewer_id,
        ),
        altered_user=(
            await build_user_get(
                altered_user,
                storage=storage,
                viewer_id=viewer_id,
            )
            if altered_user is not None
            else None
        ),
    )
