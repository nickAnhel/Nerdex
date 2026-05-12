from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, NoResultFound

from src.assets.enums import AssetStatusEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.assets.repository import AssetRepository
from src.chats.exceptions import ChatNotFound
from src.messages.exceptions import CantDeleteMessage, CantUpdateMessage, InvalidMessageAssets, InvalidMessageReply
from src.messages.presentation import DELETED_MESSAGE_STUB, build_message_get_with_user
from src.messages.repository import MessageRepository
from src.messages.schemas import (
    MessageCreate,
    MessageGet,
    MessageGetWithUser,
    MessageReplyPreview,
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
    ) -> None:
        self._repository = repostory
        self._asset_repository = asset_repository
        self._storage = storage

    async def create_message(
        self,
        message: MessageCreate,
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

            data = message.model_dump(exclude={"asset_ids"})
            if message.client_message_id is not None:
                msg = await self._repository.create_idempotent(data=data, asset_ids=asset_ids)
            else:
                msg = await self._repository.create(data=data, asset_ids=asset_ids)
            return await self._build_message_with_user(msg)
        except (IntegrityError, NoResultFound) as exc:
            raise ChatNotFound(f"Chat with id '{message.chat_id}' not found") from exc

    async def get_messages(
        self,
        *,
        chat_id: uuid.UUID,
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
        return [await self._build_message_with_user(message) for message in messages]

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

    async def search_messages(
        self,
        *,
        chat_id: uuid.UUID,
        query: str,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[MessageGetWithUser]:
        messages = await self._repository.search(
            q=query,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
            chat_id=chat_id,
        )
        return [await self._build_message_with_user(message) for message in messages]

    async def _build_message_with_user(
        self,
        message,
    ) -> MessageGetWithUser:
        return await build_message_get_with_user(message, storage=self._storage)

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
