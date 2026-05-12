import json
import uuid
from typing import Any

import socketio
from pydantic import ValidationError

from src.assets.dependencies import get_asset_service, get_asset_storage
from src.auth.socket import SocketAuthenticationError, authenticate_socket_user
from src.chats.dependencies import get_chat_service
from src.chats.exceptions import ChatNotFound
from src.chats.socket_messages import build_socket_message_create
from src.config import settings
from src.common.database import async_session_maker
from src.common.exceptions import PermissionDenied
from src.messages.dependencies import get_message_service
from src.messages.exceptions import CantDeleteMessage, CantUpdateMessage, InvalidMessageReply
from src.messages.schemas import (
    MessageCreateWS,
    MessageDeleteWS,
    MessageGetWS,
    MessageUpdate,
    MessageUpdateWS,
)
from src.users.repository import UserRepository
from src.users.service import UserService

socketio_manager = socketio.AsyncRedisManager(settings.redis.socketio_manager_url)

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=settings.ws.allowed_hosts,
    client_manager=socketio_manager,
)

socket_app = socketio.ASGIApp(
    socketio_server=sio,
    socketio_path="/ws",
)


def _success_response(data: dict[str, Any] | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {"ok": True}
    if data is not None:
        response["data"] = data
    return response


def _error_response(code: str, detail: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "detail": detail,
        },
    }


async def _get_socket_user_id(sid: str) -> uuid.UUID:
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    if not isinstance(user_id, uuid.UUID):
        raise SocketAuthenticationError("Unauthorized")

    return user_id


async def _build_message_ws_payload(message) -> dict[str, Any]:
    avatar = message.user.avatar
    return MessageGetWS(
        message_id=message.message_id,
        chat_id=message.chat_id,
        client_message_id=message.client_message_id,
        chat_seq=message.chat_seq,
        username=message.user.username,
        user_id=message.user_id,
        avatar_small_url=avatar.small_url if avatar is not None else None,
        content=message.content,
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        deleted_by=message.deleted_by,
        reply_to_message_id=message.reply_to_message_id,
        reply_preview=message.reply_preview,
    ).model_dump(mode="json")


@sio.event
async def connect(
    sid: str,
    _environ: dict[str, Any],
    auth: Any,
) -> None:
    async with async_session_maker() as session:
        user_service = UserService(
            repository=UserRepository(session),
            asset_service=await get_asset_service(async_session=session),
            avatar_storage=get_asset_storage(),
        )
        try:
            user = await authenticate_socket_user(
                auth=auth,
                user_service=user_service,
            )
        except SocketAuthenticationError as exc:
            raise socketio.exceptions.ConnectionRefusedError("Unauthorized") from exc

    await sio.save_session(sid, {"user_id": user.user_id})


@sio.on("join")
async def on_join(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        chat_id = uuid.UUID(str(data["chat_id"]))
        user_id = await _get_socket_user_id(sid)
    except (KeyError, TypeError, ValueError):
        return _error_response("bad_request", "Invalid chat_id")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        service = get_chat_service(session)
        try:
            await service.ensure_user_is_chat_member(
                chat_id=chat_id,
                user_id=user_id,
            )
        except ChatNotFound as exc:
            return _error_response("not_found", str(exc))
        except PermissionDenied as exc:
            return _error_response("forbidden", str(exc))

    await sio.enter_room(sid, str(chat_id))
    return _success_response()


@sio.on("leave")
async def on_leave(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        chat_id = uuid.UUID(str(data["chat_id"]))
    except (KeyError, TypeError, ValueError):
        return _error_response("bad_request", "Invalid chat_id")

    await sio.leave_room(sid, str(chat_id))
    return _success_response()


@sio.on("message")
async def on_message(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        user_id = await _get_socket_user_id(sid)
        msg = MessageCreateWS.model_validate(data)
        chat_id = msg.chat_id
    except (KeyError, TypeError, ValueError, ValidationError):
        return _error_response("bad_request", "Invalid message payload")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        chat_service = get_chat_service(session)
        try:
            await chat_service.ensure_user_is_chat_member(
                chat_id=chat_id,
                user_id=user_id,
            )
        except ChatNotFound as exc:
            return _error_response("not_found", str(exc))
        except PermissionDenied as exc:
            return _error_response("forbidden", str(exc))

        message_service = get_message_service(session)
        try:
            message = await message_service.create_message(
                build_socket_message_create(
                    chat_id=chat_id,
                    user_id=user_id,
                    msg=msg,
                )
            )
        except InvalidMessageReply as exc:
            return _error_response("bad_request", str(exc))
    message_payload = await _build_message_ws_payload(message)

    await sio.emit(
        "message:created",
        message_payload,
        room=str(chat_id),
    )
    await sio.emit(
        "message",
        json.dumps(message_payload),
        room=str(chat_id),
        skip_sid=sid,
    )
    return _success_response(message_payload)


@sio.on("message:update")
async def on_message_update(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        user_id = await _get_socket_user_id(sid)
        msg = MessageUpdateWS.model_validate(data)
    except (KeyError, TypeError, ValueError, ValidationError):
        return _error_response("bad_request", "Invalid message update payload")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        message_service = get_message_service(session)
        try:
            message = await message_service.update_message(
                data=MessageUpdate(content=msg.content),
                message_id=msg.message_id,
                user_id=user_id,
            )
        except CantUpdateMessage as exc:
            return _error_response("forbidden", str(exc))

    message_payload = await _build_message_ws_payload(message)
    await sio.emit(
        "message:updated",
        message_payload,
        room=str(message.chat_id),
    )
    return _success_response(message_payload)


@sio.on("message:delete")
async def on_message_delete(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        user_id = await _get_socket_user_id(sid)
        msg = MessageDeleteWS.model_validate(data)
    except (KeyError, TypeError, ValueError, ValidationError):
        return _error_response("bad_request", "Invalid message delete payload")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        message_service = get_message_service(session)
        try:
            message = await message_service.delete_message(
                message_id=msg.message_id,
                user_id=user_id,
            )
        except CantDeleteMessage as exc:
            return _error_response("forbidden", str(exc))

    message_payload = await _build_message_ws_payload(message)
    await sio.emit(
        "message:deleted",
        message_payload,
        room=str(message.chat_id),
    )
    return _success_response(message_payload)
