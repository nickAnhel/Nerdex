import uuid

from fastapi import APIRouter, Depends

from src.auth.dependencies import get_current_user
from src.chats.sockets import _build_message_ws_payload, sio
from src.chats.dependencies import get_chat_service
from src.chats.service import ChatService
from src.messages.dependencies import get_message_service
from src.messages.enums import MessagesOrder
from src.messages.schemas import MessageGetWithUser, MessageUpdate, SharedContentMessagesCreate
from src.messages.service import MessageService
from src.common.schemas import Status
from src.users.schemas import UserGet

router = APIRouter(
    prefix="/messages",
    tags=["Messages"],
)


@router.get("/")
async def get_chat_messages(
    chat_id: uuid.UUID,
    order: MessagesOrder = MessagesOrder.CREATED_AT,
    offset: int = 0,
    limit: int = 100,
    user: UserGet = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[MessageGetWithUser]:
    await chat_service.ensure_user_is_chat_member(chat_id=chat_id, user_id=user.user_id)
    return await service.get_messages(
        chat_id=chat_id,
        viewer_id=user.user_id,
        order=order,
        order_desc=True,
        offset=offset,
        limit=limit,
    )


@router.get("/search")
async def search_chat_messages(
    chat_id: uuid.UUID,
    query: str,
    order: MessagesOrder = MessagesOrder.CREATED_AT,
    offset: int = 0,
    limit: int = 100,
    user: UserGet = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
    chat_service: ChatService = Depends(get_chat_service),
) -> list[MessageGetWithUser]:
    await chat_service.ensure_user_is_chat_member(chat_id=chat_id, user_id=user.user_id)
    return await service.search_messages(
        chat_id=chat_id,
        viewer_id=user.user_id,
        query=query,
        order=order,
        order_desc=True,
        offset=offset,
        limit=limit,
    )


@router.post("/share-content")
async def share_content_to_chats(
    data: SharedContentMessagesCreate,
    user: UserGet = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> list[MessageGetWithUser]:
    messages = await service.share_content_to_chats(
        data=data,
        user_id=user.user_id,
    )
    for message in messages:
        await sio.emit(
            "message:created",
            await _build_message_ws_payload(message),
            room=str(message.chat_id),
        )
    return messages


@router.delete("/")
async def clear_chat_messages(
    chat_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    message_service: MessageService = Depends(get_message_service),
    chat_service: ChatService = Depends(get_chat_service),
) -> Status:
    await chat_service.check_chat_exists_and_user_is_owner(
        chat_id=chat_id, user_id=user.user_id
    )
    deleted_messages_count = await message_service.delete_messages(chat_id=chat_id)
    return Status(detail=f"Successfully deleted {deleted_messages_count} messages")


@router.delete("/{message_id}")
async def delete_message(
    message_id: uuid.UUID,
    user: UserGet = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> Status:
    await service.delete_message(message_id=message_id, user_id=user.user_id)
    return Status(detail="Successfully deleted message")


@router.patch("/{message_id}")
async def update_message(
    message_id: uuid.UUID,
    data: MessageUpdate,
    user: UserGet = Depends(get_current_user),
    service: MessageService = Depends(get_message_service),
) -> MessageGetWithUser:
    return await service.update_message(
        data=data,
        message_id=message_id,
        user_id=user.user_id,
    )
