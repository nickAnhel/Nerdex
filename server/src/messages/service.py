from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, NoResultFound

from src.assets.enums import AssetStatusEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.assets.repository import AssetRepository
from src.chats.exceptions import ChatNotFound
from src.chats.repository import ChatRepository
from src.common.exceptions import PermissionDenied
from src.content.enums import ReactionTypeEnum
from src.content.schemas import ContentListItemGet
from src.content.service import ContentService
from src.messages.exceptions import (
    CantDeleteMessage,
    CantReactToMessage,
    CantUpdateMessage,
    InvalidMessageAssets,
    InvalidMessageReply,
)
from src.messages.presentation import DELETED_MESSAGE_STUB, build_message_get_with_user
from src.messages.repository import MessageRepository
from src.messages.schemas import (
    MessageCreate,
    MessageGetWithUser,
    MessageReplyPreview,
    MessageSearchGet,
    SharedContentMessagesCreate,
    MessageUpdate,
)

if TYPE_CHECKING:
    from src.assets.storage import AssetStorage


class MessageService:
    def __init__(
        self,
        repostory: MessageRepository,
        asset_repository: AssetRepository | None = None,
        storage: AssetStorage | None = None,
        chat_repository: ChatRepository | None = None,
        content_service: ContentService | None = None,
    ) -> None:
        self._repository = repostory
        self._asset_repository = asset_repository
        self._storage = storage
        self._chat_repository = chat_repository
        self._content_service = content_service

    async def create_message(
        self,
        message: MessageCreate,
        *,
        validate_shared_content: bool = True,
        shared_content_preview: ContentListItemGet | None = None,
    ) -> MessageGetWithUser:
        try:
            asset_ids = self._dedupe_asset_ids(message.asset_ids)
            if asset_ids:
                await self._ensure_assets_can_be_attached(
                    asset_ids=asset_ids,
                    owner_id=message.user_id,
                )

            if message.reply_to_message_id is not None:
                await self._ensure_reply_target_belongs_to_chat(
                    reply_to_message_id=message.reply_to_message_id,
                    chat_id=message.chat_id,
                )
            if message.shared_content_id is not None and validate_shared_content:
                if self._content_service is None:
                    raise InvalidMessageAssets("Shared content messages are not configured")
                shared_content_preview = await self._content_service.get_shareable_content(
                    content_id=message.shared_content_id,
                    viewer_id=message.user_id,
                )

            data = message.model_dump(exclude={"asset_ids", "shared_content_id"})
            if message.client_message_id is not None:
                msg = await self._repository.create_idempotent(
                    data=data,
                    asset_ids=asset_ids,
                    shared_content_id=message.shared_content_id,
                )
            else:
                msg = await self._repository.create(
                    data=data,
                    asset_ids=asset_ids,
                    shared_content_id=message.shared_content_id,
                )
            return await self._build_message_with_user(
                msg,
                shared_content_preview=shared_content_preview,
            )
        except (IntegrityError, NoResultFound) as exc:
            raise ChatNotFound(f"Chat with id '{message.chat_id}' not found") from exc

    async def share_content_to_chats(
        self,
        *,
        data: SharedContentMessagesCreate,
        user_id: uuid.UUID,
    ) -> list[MessageGetWithUser]:
        if self._chat_repository is None:
            raise PermissionDenied("Chat access checks are not configured")
        if self._content_service is None:
            raise InvalidMessageAssets("Shared content messages are not configured")

        chat_ids = list(dict.fromkeys(data.chat_ids))
        for chat_id in chat_ids:
            if not await self._chat_repository.is_member(chat_id=chat_id, user_id=user_id):
                raise PermissionDenied(
                    f"User with id '{user_id}' is not a member of chat with id '{chat_id}'"
                )

        shared_content_preview = await self._content_service.get_shareable_content(
            content_id=data.content_id,
            viewer_id=user_id,
        )

        created: list[MessageGetWithUser] = []
        for chat_id in chat_ids:
            created.append(
                await self.create_message(
                    MessageCreate(
                        chat_id=chat_id,
                        user_id=user_id,
                        content=data.content,
                        shared_content_id=data.content_id,
                    ),
                    validate_shared_content=False,
                    shared_content_preview=shared_content_preview,
                )
            )
        return created

    async def get_messages(
        self,
        *,
        chat_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[MessageGetWithUser]:
        messages = await self._repository.get_multi(
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
            chat_id=chat_id,
        )
        return [
            await self._build_message_with_user(message, viewer_id=viewer_id)
            for message in messages
        ]

    async def delete_message(
        self,
        *,
        user_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> MessageGetWithUser:
        try:
            message = await self._repository.soft_delete(
                message_id=message_id,
                user_id=user_id,
            )
        except NoResultFound as exc:
            raise CantDeleteMessage(
                f"Message with id '{message_id}' and user_id '{user_id}' not found"
            ) from exc

        return await self._build_message_with_user(message)

    async def delete_messages(
        self,
        *,
        chat_id: uuid.UUID,
    ) -> int:
        return await self._repository.delete_multi(chat_id=chat_id)

    async def update_message(
        self,
        *,
        data: MessageUpdate,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MessageGetWithUser:
        try:
            message = await self._repository.update(
                data=data.model_dump(exclude_none=True),
                message_id=message_id,
                user_id=user_id,
            )
        except NoResultFound as exc:
            raise CantUpdateMessage(
                f"Message with id '{message_id}' and user_id '{user_id}' not found"
            ) from exc

        return await self._build_message_with_user(message)

    async def set_message_reaction(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> tuple[MessageGetWithUser, ReactionTypeEnum | None]:
        message = await self._get_reactable_message(
            message_id=message_id,
            user_id=user_id,
        )
        previous_reaction_type = self._get_user_reaction_type(message, user_id=user_id)
        reacted_message = await self._repository.set_reaction(
            message_id=message.message_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        return (
            await self._build_message_with_user(
                reacted_message,
                viewer_id=user_id,
            ),
            previous_reaction_type,
        )

    async def remove_message_reaction(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> tuple[MessageGetWithUser, ReactionTypeEnum | None]:
        message = await self._get_reactable_message(
            message_id=message_id,
            user_id=user_id,
        )
        previous_reaction_type = self._get_user_reaction_type(message, user_id=user_id)
        reacted_message = await self._repository.remove_reaction(
            message_id=message.message_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        return (
            await self._build_message_with_user(
                reacted_message,
                viewer_id=user_id,
            ),
            previous_reaction_type,
        )

    async def udpate_message(
        self,
        *,
        data: MessageUpdate,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MessageGetWithUser:
        return await self.update_message(
            data=data,
            message_id=message_id,
            user_id=user_id,
        )

    async def _ensure_reply_target_belongs_to_chat(
        self,
        *,
        reply_to_message_id: uuid.UUID,
        chat_id: uuid.UUID,
    ) -> None:
        try:
            reply_target = await self._repository.get_reply_target(
                message_id=reply_to_message_id,
            )
        except NoResultFound as exc:
            raise InvalidMessageReply(
                f"Reply target message with id '{reply_to_message_id}' not found"
            ) from exc

        if reply_target.chat_id != chat_id:
            raise InvalidMessageReply(
                f"Reply target message with id '{reply_to_message_id}' belongs to another chat"
            )

    async def _get_reactable_message(
        self,
        *,
        message_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        if self._chat_repository is None:
            raise PermissionDenied("Chat access checks are not configured")

        try:
            message = await self._repository.get_single(message_id=message_id)
        except NoResultFound as exc:
            raise CantReactToMessage(f"Message with id '{message_id}' not found") from exc

        if message.deleted_at is not None:
            raise CantReactToMessage(f"Message with id '{message_id}' is deleted")

        if not await self._chat_repository.is_member(chat_id=message.chat_id, user_id=user_id):
            raise PermissionDenied(
                f"User with id '{user_id}' is not a member of chat with id '{message.chat_id}'"
            )

        return message

    def _get_user_reaction_type(
        self,
        message,
        *,
        user_id: uuid.UUID,
    ) -> ReactionTypeEnum | None:
        for reaction in getattr(message, "reactions", []):
            if getattr(reaction, "user_id", None) == user_id:
                return getattr(reaction, "reaction_type", None)
        return None

    async def search_messages(
        self,
        *,
        chat_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
        query: str,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> MessageSearchGet:
        normalized_query = query.strip()
        if not normalized_query:
            return MessageSearchGet(items=[], total=0, offset=offset, limit=limit)

        messages, total = await self._repository.search(
            query_text=normalized_query,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
            chat_id=chat_id,
        )
        items = [
            await self._build_message_with_user(message, viewer_id=viewer_id)
            for message in messages
        ]
        return MessageSearchGet(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
        )

    async def _build_message_with_user(
        self,
        message,
        *,
        viewer_id: uuid.UUID | None = None,
        shared_content_preview: ContentListItemGet | None = None,
    ) -> MessageGetWithUser:
        return await build_message_get_with_user(
            message,
            storage=self._storage,
            content_service=self._content_service,
            viewer_id=viewer_id or message.user_id,
            shared_content_preview=shared_content_preview,
        )

    def _build_reply_preview(self, message) -> MessageReplyPreview:
        deleted = message.deleted_at is not None
        return MessageReplyPreview(
            message_id=message.message_id,
            sender_display_name=message.user.username,
            content_preview=DELETED_MESSAGE_STUB if deleted else message.content_ellipsis,
            deleted=deleted,
        )

    def _dedupe_asset_ids(self, asset_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(asset_ids))

    async def _ensure_assets_can_be_attached(
        self,
        *,
        asset_ids: list[uuid.UUID],
        owner_id: uuid.UUID,
    ) -> None:
        if self._asset_repository is None:
            raise InvalidMessageAssets("Message attachments are not configured")

        assets = await self._asset_repository.get_assets(asset_ids=asset_ids, owner_id=owner_id)
        assets_by_id = {asset.asset_id: asset for asset in assets}
        missing_asset_ids = [asset_id for asset_id in asset_ids if asset_id not in assets_by_id]
        if missing_asset_ids:
            raise InvalidMessageAssets(
                "Some message attachments are unavailable for this user: "
                + ", ".join(str(asset_id) for asset_id in missing_asset_ids)
            )

        for asset_id in asset_ids:
            asset = assets_by_id[asset_id]
            if asset.status not in {
                AssetStatusEnum.UPLOADED,
                AssetStatusEnum.PROCESSING,
                AssetStatusEnum.READY,
            }:
                raise InvalidMessageAssets(f"Asset {asset_id} is not ready to attach")

            original_variant = next(
                (
                    variant
                    for variant in getattr(asset, "variants", [])
                    if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL
                ),
                None,
            )
            if original_variant is None or original_variant.status != AssetVariantStatusEnum.READY:
                raise InvalidMessageAssets(f"Asset {asset_id} original file is not available")
