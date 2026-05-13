from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, NoResultFound

from src.chats.enums import ChatMemberRole, ChatOrder, ChatType
from src.chats.exceptions import (
    AlreadyInChat,
    CantAddMembers,
    CantRemoveMembers,
    ChatNotFound,
    FailedToLeaveChat,
    InvalidChatHistoryCursor,
)
from src.chats.repository import ChatRepository
from src.chats.schemas import (
    ChatCreate,
    ChatDialogGet,
    ChatGet,
    ChatUpdate,
    EventHistoryItem,
    MessageHistoryItem,
)
from src.common.exceptions import PermissionDenied
from src.content.service import ContentService
from src.messages.models import MessageModel
from src.messages.presentation import build_message_get_with_user, build_reply_preview
from src.messages.schemas import MessageGetWithUser, MessageReplyPreview
from src.users.presentation import build_user_get
from src.users.schemas import UserGet

if TYPE_CHECKING:
    from src.assets.storage import AssetStorage


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        storage: AssetStorage | None = None,
        content_service: ContentService | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._content_service = content_service

    async def create_chat(
        self,
        user_id: uuid.UUID,
        data: ChatCreate,
    ) -> ChatGet:
        if data.chat_type == ChatType.DIRECT:
            return await self._create_direct_chat(user_id=user_id, data=data)

        return await self._create_group_chat(user_id=user_id, data=data)

    async def _create_direct_chat(
        self,
        *,
        user_id: uuid.UUID,
        data: ChatCreate,
    ) -> ChatGet:
        if data.member_id is None:
            raise CantAddMembers("Direct chat member is required")

        if data.member_id == user_id:
            raise CantAddMembers("Can't create direct chat with yourself")

        direct_key = self._build_direct_key(user_id, data.member_id)
        if existing_chat := await self._repository.get_by_direct_key(direct_key):
            return await self._build_chat_get(existing_chat)

        try:
            chat = await self._repository.create_with_member_roles(
                data={
                    "title": "Direct chat",
                    "is_private": True,
                    "chat_type": ChatType.DIRECT.value,
                    "direct_key": direct_key,
                    "owner_id": user_id,
                },
                member_roles=[
                    (user_id, ChatMemberRole.OWNER),
                    (data.member_id, ChatMemberRole.MEMBER),
                ],
            )
        except IntegrityError as exc:
            if existing_chat := await self._repository.get_by_direct_key(direct_key):
                return await self._build_chat_get(existing_chat)
            raise CantAddMembers("Can't add members") from exc

        chat = await self._repository.get_single(chat_id=chat.chat_id)
        return await self._build_chat_get(chat)

    async def _create_group_chat(
        self,
        *,
        user_id: uuid.UUID,
        data: ChatCreate,
    ) -> ChatGet:
        member_ids = list(dict.fromkeys(data.members))
        member_roles = [(user_id, ChatMemberRole.OWNER)]
        member_roles.extend(
            (member_id, ChatMemberRole.MEMBER)
            for member_id in member_ids
            if member_id != user_id
        )

        try:
            chat = await self._repository.create_with_member_roles(
                data={
                    "title": data.title,
                    "is_private": data.is_private,
                    "chat_type": ChatType.GROUP.value,
                    "owner_id": user_id,
                },
                member_roles=member_roles,
            )
        except IntegrityError as exc:
            raise CantAddMembers("Can't add members") from exc

        chat = await self._repository.get_single(chat_id=chat.chat_id)
        return await self._build_chat_get(chat)

    async def get_chat(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> ChatGet:
        try:
            chat = await self._repository.get_single(chat_id=chat_id)
            if user_id is not None:
                await self._ensure_user_can_view_chat(chat=chat, user_id=user_id)
            return await self._build_chat_get(chat)
        except NoResultFound as exc:
            raise ChatNotFound(f"Chat with id '{chat_id}' not found") from exc

    async def get_chat_members(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> list[UserGet]:
        try:
            if user_id is not None:
                chat = await self._repository.get_single(chat_id=chat_id)
                await self._ensure_user_can_view_chat(chat=chat, user_id=user_id)
            members = await self._repository.get_members(chat_id=chat_id)
            return [await build_user_get(member) for member in members]
        except NoResultFound as exc:
            raise ChatNotFound(f"Chat with id '{chat_id}' not found") from exc

    async def get_chats(
        self,
        *,
        order: ChatOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ChatGet]:
        chats = await self._repository.get_multi(
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_chat_get(chat) for chat in chats]

    async def get_chat_history(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        limit: int,
        before_seq: int | None = None,
        after_seq: int | None = None,
    ) -> list[MessageHistoryItem | EventHistoryItem]:
        if before_seq is not None and after_seq is not None:
            raise InvalidChatHistoryCursor(
                "Use either before_seq or after_seq, not both"
            )

        if user_id is not None:
            try:
                chat = await self._repository.get_single(chat_id=chat_id)
            except NoResultFound as exc:
                raise ChatNotFound(f"Chat with id '{chat_id}' not found") from exc
            await self._ensure_user_can_view_chat(chat=chat, user_id=user_id)
            can_access_message_assets = await self._repository.is_member(
                chat_id=chat_id,
                user_id=user_id,
            )
        else:
            can_access_message_assets = False

        history = await self._repository.history(
            chat_id=chat_id,
            limit=limit,
            before_seq=before_seq,
            after_seq=after_seq,
        )

        items: list[MessageHistoryItem | EventHistoryItem] = []
        for _timeline_item, item in history:
            if isinstance(item, MessageModel):
                message = await self._build_message_get_with_user(
                    item,
                    viewer_id=user_id,
                    include_attachments=can_access_message_assets,
                )
                items.append(MessageHistoryItem(**message.model_dump()))
            else:
                items.append(EventHistoryItem.model_validate(item))

        return items

    async def join_chat(
        self,
        *,
        chat_id: uuid.UUID,
        user: UserGet,
    ) -> bool:
        try:
            if not user.is_admin:
                chat = await self._repository.get_single(chat_id=chat_id)
                if chat.chat_type == ChatType.DIRECT.value or chat.is_private:
                    raise PermissionDenied(f"Chat with id '{chat_id}' is private")

            return (
                await self._repository.add_members(
                    chat_id=chat_id,
                    users_ids=[user.user_id],
                    role=ChatMemberRole.MEMBER,
                )
                == 1
            )

        except NoResultFound as exc:
            raise ChatNotFound(f"Chat with id '{chat_id}' not found") from exc

        except IntegrityError as exc:
            raise AlreadyInChat(
                f"User with id '{user.user_id}' already in chat"
            ) from exc

    async def leave_chat(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        if (
            await self._repository.remove_members(
                chat_id=chat_id, members_ids=[user_id]
            )
            != 1
        ):
            raise FailedToLeaveChat(f"Failed to leave chat with id '{chat_id}'")

        # Delete chat if it has no members
        if len(await self._repository.get_members(chat_id=chat_id)) == 0:
            await self._repository.delete(chat_id=chat_id)

    async def check_chat_exists_and_user_is_owner(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        try:
            chat = await self._repository.get_single(chat_id=chat_id)
        except NoResultFound as exc:
            raise ChatNotFound(f"Chat with id '{chat_id}' not found") from exc

        is_owner_member = await self._repository.is_owner_member(
            chat_id=chat_id,
            user_id=user_id,
        )
        if chat.owner_id != user_id and not is_owner_member:
            raise PermissionDenied(
                f"User with id '{user_id}' is not owner of chat with id '{chat_id}'"
            )
        return chat

    async def ensure_user_is_chat_member(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        if await self._repository.is_member(chat_id=chat_id, user_id=user_id):
            return

        try:
            await self._repository.get_single(chat_id=chat_id)
        except NoResultFound as exc:
            raise ChatNotFound(f"Chat with id '{chat_id}' not found") from exc

        raise PermissionDenied(
            f"User with id '{user_id}' is not a member of chat with id '{chat_id}'"
        )

    async def add_members_to_chat(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        members_ids: list[uuid.UUID],
    ) -> int:
        chat = await self.check_chat_exists_and_user_is_owner(chat_id=chat_id, user_id=user_id)

        if chat.chat_type == ChatType.DIRECT.value:
            raise CantAddMembers("Can't add members to direct chat")

        if user_id in members_ids:
            raise CantAddMembers("Can't add yourself to chat")

        try:
            if (
                added_users_count := await self._repository.add_members(
                    chat_id=chat_id,
                    users_ids=members_ids,
                )
            ) == 0:
                raise CantAddMembers("Failed to add members")

            return added_users_count
        except IntegrityError as exc:
            raise CantAddMembers("Can't add members") from exc

    async def remove_members_from_chat(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        members_ids: list[uuid.UUID],
    ) -> int:
        chat = await self.check_chat_exists_and_user_is_owner(chat_id=chat_id, user_id=user_id)

        if chat.chat_type == ChatType.DIRECT.value:
            raise CantRemoveMembers("Can't remove members from direct chat")

        if user_id in members_ids:
            raise CantAddMembers("Can't remove yourself from chat")

        if (
            removed_users_count := await self._repository.remove_members(
                chat_id=chat_id,
                members_ids=members_ids,
            )
        ) == 0:
            raise CantRemoveMembers("Can't remove members")

        return removed_users_count

    async def update_chat(
        self,
        *,
        data: ChatUpdate,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ChatGet:
        await self.check_chat_exists_and_user_is_owner(chat_id=chat_id, user_id=user_id)
        chat = await self._repository.update(
            data=data.model_dump(exclude_none=True),
            chat_id=chat_id,
        )
        return await self._build_chat_get(chat)

    async def delete_chat(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        await self.check_chat_exists_and_user_is_owner(chat_id=chat_id, user_id=user_id)
        await self._repository.delete(chat_id=chat_id)

    async def search_chats(
        self,
        *,
        user_id: uuid.UUID,
        query: str,
        offset: int,
        limit: int,
    ) -> list[ChatGet]:
        chats = await self._repository.search(
            user_id=user_id,
            q=query,
            offset=offset,
            limit=limit,
        )
        return [await self._build_chat_get(chat) for chat in chats]

    async def get_user_joined_chats(
        self,
        user: UserGet,
        order: ChatOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[ChatDialogGet]:
        chats = await self._repository.get_user_dialogs(
            user_id=user.user_id,
            offset=offset,
            limit=limit,
        )
        return [
            await self._build_chat_dialog_get(chat, user_id=user.user_id)
            for chat in chats
        ]

    async def mark_chat_read(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> uuid.UUID | None:
        await self.ensure_user_is_chat_member(chat_id=chat_id, user_id=user_id)
        return await self._repository.mark_read(chat_id=chat_id, user_id=user_id)

    async def _build_chat_get(self, chat) -> ChatGet:
        return ChatGet(
            chat_id=chat.chat_id,
            title=chat.title,
            is_private=chat.is_private,
            chat_type=chat.chat_type,
            owner_id=chat.owner_id,
            members=[
                await build_user_get(member)
                for member in getattr(chat, "members", [])
            ],
        )

    async def _build_chat_dialog_get(
        self,
        chat,
        *,
        user_id: uuid.UUID,
    ) -> ChatDialogGet:
        chat_get = await self._build_chat_get(chat)
        direct_member = None
        if chat.chat_type == ChatType.DIRECT.value:
            direct_member = next(
                (
                    member
                    for member in chat_get.members
                    if member.user_id != user_id
                ),
                None,
            )

        last_message = getattr(chat, "last_message", None)
        membership = getattr(chat, "membership", None)

        return ChatDialogGet(
            **chat_get.model_dump(),
            display_title=direct_member.username if direct_member is not None else chat.title,
            display_avatar=direct_member.avatar if direct_member is not None else None,
            last_message=(
                await self._build_message_get_with_user(last_message, viewer_id=user_id)
                if last_message is not None
                else None
            ),
            last_message_at=getattr(chat, "last_message_at", None),
            unread_count=getattr(chat, "unread_count", 0),
            is_muted=(
                getattr(membership, "is_muted", False)
                if membership is not None
                else False
            ),
            last_read_message_id=(
                getattr(membership, "last_read_message_id", None)
                if membership is not None
                else None
            ),
        )

    async def _build_message_get_with_user(
        self,
        message,
        *,
        viewer_id: uuid.UUID | None = None,
        include_attachments: bool = True,
    ) -> MessageGetWithUser:
        return await build_message_get_with_user(
            message,
            storage=self._storage,
            content_service=self._content_service,
            viewer_id=viewer_id,
            include_attachments=include_attachments,
        )

    def _build_reply_preview(self, message) -> MessageReplyPreview:
        return build_reply_preview(message)

    def _build_direct_key(
        self,
        user_id: uuid.UUID,
        member_id: uuid.UUID,
    ) -> str:
        return ":".join(sorted([str(user_id), str(member_id)]))

    async def _ensure_user_can_view_chat(
        self,
        *,
        chat,
        user_id: uuid.UUID,
    ) -> None:
        if chat.chat_type == ChatType.GROUP.value and not chat.is_private:
            return

        if await self._repository.is_member(chat_id=chat.chat_id, user_id=user_id):
            return

        raise PermissionDenied(
            f"User with id '{user_id}' is not a member of chat with id '{chat.chat_id}'"
        )
