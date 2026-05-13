import json
import uuid
from typing import Any

import socketio
from pydantic import ValidationError

from src.assets.dependencies import get_asset_service, get_asset_storage
from src.auth.socket import SocketAuthenticationError, authenticate_socket_user
from src.chats.dependencies import get_chat_service
from src.chats.exceptions import ChatNotFound
from src.chats import typing_state
from src.chats.schemas import ChatTypingWS
from src.chats.socket_messages import build_socket_message_create
from src.chats.socket_messages import build_socket_typing_status
from src.config import settings
from src.common.database import async_session_maker
from src.common.exceptions import PermissionDenied
from src.content.exceptions import ContentNotFound
from src.messages.dependencies import get_message_service
from src.messages.exceptions import (
    CantDeleteMessage,
    CantReactToMessage,
    CantUpdateMessage,
    InvalidMessageAssets,
    InvalidMessageReply,
)
from src.messages.schemas import (
    MessageCreateWS,
    MessageDeleteWS,
    MessageGetWS,
    MessageReactionEventWS,
    MessageReactionWS,
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
    user_id, _username = await _get_socket_user_context(sid)
    return user_id


async def _get_socket_user_context(sid: str) -> tuple[uuid.UUID, str]:
    session = await sio.get_session(sid)
    user_id = session.get("user_id")
    username = session.get("username")
    if not isinstance(user_id, uuid.UUID) or not isinstance(username, str) or not username:
        raise SocketAuthenticationError("Unauthorized")

    return user_id, username


async def _build_message_ws_payload(message, *, viewer_id: uuid.UUID | None = None) -> dict[str, Any]:
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
        attachments=message.attachments,
        shared_content=message.shared_content,
        reactions=message.reactions,
    ).model_dump(mode="json")


def _build_message_reaction_event_payload(
    *,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    reaction_type: Any,
    previous_reaction_type: Any = None,
    action: str,
) -> dict[str, Any]:
    return MessageReactionEventWS(
        message_id=message_id,
        user_id=user_id,
        reaction_type=reaction_type,
        previous_reaction_type=previous_reaction_type,
        action=action,
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

    await sio.save_session(
        sid,
        {
            "user_id": user.user_id,
            "username": user.username,
        },
    )


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


@sio.on("typing:start")
async def on_typing_start(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        msg = ChatTypingWS.model_validate(data)
        user_id, username = await _get_socket_user_context(sid)
    except (KeyError, TypeError, ValueError, ValidationError):
        return _error_response("bad_request", "Invalid typing payload")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        service = get_chat_service(session)
        try:
            await service.ensure_user_is_chat_member(
                chat_id=msg.chat_id,
                user_id=user_id,
            )
        except ChatNotFound as exc:
            return _error_response("not_found", str(exc))
        except PermissionDenied as exc:
            return _error_response("forbidden", str(exc))

    await typing_state.mark_chat_typing(
        chat_id=msg.chat_id,
        user_id=user_id,
        username=username,
    )
    payload = build_socket_typing_status(
        chat_id=msg.chat_id,
        user_id=user_id,
        username=username,
        expires_in_seconds=typing_state.TYPING_STATUS_EXPIRES_IN_SECONDS,
    )
    await sio.emit(
        "typing:start",
        payload,
        room=str(msg.chat_id),
        skip_sid=sid,
    )
    return _success_response(
        {"expires_in_seconds": typing_state.TYPING_STATUS_EXPIRES_IN_SECONDS}
    )


@sio.on("typing:stop")
async def on_typing_stop(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        msg = ChatTypingWS.model_validate(data)
        user_id, username = await _get_socket_user_context(sid)
    except (KeyError, TypeError, ValueError, ValidationError):
        return _error_response("bad_request", "Invalid typing payload")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        service = get_chat_service(session)
        try:
            await service.ensure_user_is_chat_member(
                chat_id=msg.chat_id,
                user_id=user_id,
            )
        except ChatNotFound as exc:
            return _error_response("not_found", str(exc))
        except PermissionDenied as exc:
            return _error_response("forbidden", str(exc))

    await typing_state.clear_chat_typing(
        chat_id=msg.chat_id,
        user_id=user_id,
    )
    await sio.emit(
        "typing:stop",
        build_socket_typing_status(
            chat_id=msg.chat_id,
            user_id=user_id,
            username=username,
            expires_in_seconds=typing_state.TYPING_STATUS_EXPIRES_IN_SECONDS,
        ),
        room=str(msg.chat_id),
        skip_sid=sid,
    )
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
        except InvalidMessageAssets as exc:
            return _error_response("bad_request", str(exc))
        except ContentNotFound as exc:
            return _error_response("forbidden", str(exc))
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


@sio.on("message:reaction:set")
async def on_message_reaction_set(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        user_id = await _get_socket_user_id(sid)
        msg = MessageReactionWS.model_validate(data)
    except (KeyError, TypeError, ValueError, ValidationError):
        return _error_response("bad_request", "Invalid message reaction payload")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        message_service = get_message_service(session)
        try:
            message, previous_reaction_type = await message_service.set_message_reaction(
                message_id=msg.message_id,
                user_id=user_id,
                reaction_type=msg.reaction_type,
            )
        except PermissionDenied as exc:
            return _error_response("forbidden", str(exc))
        except CantReactToMessage as exc:
            return _error_response("bad_request", str(exc))

    message_payload = _build_message_reaction_event_payload(
        message_id=message.message_id,
        user_id=user_id,
        reaction_type=msg.reaction_type,
        previous_reaction_type=previous_reaction_type,
        action="added",
    )
    await sio.emit(
        "message:reaction:added",
        message_payload,
        room=str(message.chat_id),
        skip_sid=sid,
    )
    return _success_response(await _build_message_ws_payload(message))


@sio.on("message:reaction:remove")
async def on_message_reaction_remove(
    sid: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    try:
        user_id = await _get_socket_user_id(sid)
        msg = MessageReactionWS.model_validate(data)
    except (KeyError, TypeError, ValueError, ValidationError):
        return _error_response("bad_request", "Invalid message reaction payload")
    except SocketAuthenticationError as exc:
        return _error_response("unauthorized", str(exc))

    async with async_session_maker() as session:
        message_service = get_message_service(session)
        try:
            message, previous_reaction_type = await message_service.remove_message_reaction(
                message_id=msg.message_id,
                user_id=user_id,
                reaction_type=msg.reaction_type,
            )
        except PermissionDenied as exc:
            return _error_response("forbidden", str(exc))
        except CantReactToMessage as exc:
            return _error_response("bad_request", str(exc))

    message_payload = _build_message_reaction_event_payload(
        message_id=message.message_id,
        user_id=user_id,
        reaction_type=msg.reaction_type,
        previous_reaction_type=previous_reaction_type,
        action="removed",
    )
    await sio.emit(
        "message:reaction:removed",
        message_payload,
        room=str(message.chat_id),
        skip_sid=sid,
    )
    return _success_response(await _build_message_ws_payload(message))
