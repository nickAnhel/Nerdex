from __future__ import annotations

import typing as tp
import uuid

from src.assets.enums import AssetTypeEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.messages.schemas import MessageAttachmentGet, MessageGetWithUser, MessageReplyPreview
from src.users.presentation import build_user_get

if tp.TYPE_CHECKING:
    from src.assets.storage import AssetStorage


DELETED_MESSAGE_STUB = "Message deleted"
IMAGE_PREVIEW_VARIANTS = (
    AssetVariantTypeEnum.IMAGE_SMALL,
    AssetVariantTypeEnum.IMAGE_MEDIUM,
    AssetVariantTypeEnum.ORIGINAL,
)
VIDEO_PREVIEW_VARIANTS = (
    AssetVariantTypeEnum.VIDEO_PREVIEW_SMALL,
    AssetVariantTypeEnum.VIDEO_PREVIEW_MEDIUM,
    AssetVariantTypeEnum.VIDEO_PREVIEW_ORIGINAL,
)


async def build_message_get_with_user(
    message: tp.Any,
    *,
    storage: AssetStorage | None = None,
    include_attachments: bool = True,
) -> MessageGetWithUser:
    reply_to_message = getattr(message, "reply_to_message", None)
    deleted_at = getattr(message, "deleted_at", None)
    return MessageGetWithUser(
        message_id=message.message_id,
        chat_id=message.chat_id,
        client_message_id=message.client_message_id,
        content=DELETED_MESSAGE_STUB if deleted_at is not None else message.content,
        user_id=message.user_id,
        asset_ids=[
            link.asset_id
            for link in sorted(_active_asset_links(message), key=lambda item: item.sort_order)
        ],
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=deleted_at,
        deleted_by=message.deleted_by,
        chat_seq=getattr(message, "chat_seq", None),
        reply_to_message_id=getattr(message, "reply_to_message_id", None),
        reply_preview=(
            build_reply_preview(reply_to_message)
            if reply_to_message is not None
            else None
        ),
        attachments=(
            []
            if deleted_at is not None or not include_attachments
            else await build_message_attachments(message, storage=storage)
        ),
        user=await build_user_get(message.user, storage=storage),
    )


async def build_message_attachments(
    message: tp.Any,
    *,
    storage: AssetStorage | None,
) -> list[MessageAttachmentGet]:
    attachments: list[MessageAttachmentGet] = []
    for link in sorted(_active_asset_links(message), key=lambda item: item.sort_order):
        attachment = await build_message_attachment_get(link, storage=storage)
        if attachment is not None:
            attachments.append(attachment)
    return attachments


async def build_message_attachment_get(
    link: tp.Any,
    *,
    storage: AssetStorage | None,
) -> MessageAttachmentGet | None:
    asset = getattr(link, "asset", None)
    if asset is None:
        return None

    original_variant = _pick_variant(asset, AssetVariantTypeEnum.ORIGINAL)
    preview_variant = _pick_preview_variant(asset)
    poster_variant = _pick_video_poster_variant(asset)
    mime_type = getattr(asset, "detected_mime_type", None) or getattr(original_variant, "mime_type", None)

    original_url = await _build_variant_url(storage=storage, variant=original_variant)
    preview_url = await _build_variant_url(storage=storage, variant=preview_variant) or original_url
    stream_url = original_url
    download_url = await _build_variant_download_url(
        storage=storage,
        variant=original_variant,
        filename=getattr(asset, "original_filename", None),
        mime_type=mime_type,
    )
    width = getattr(preview_variant, "width", None) or getattr(original_variant, "width", None)
    height = getattr(preview_variant, "height", None) or getattr(original_variant, "height", None)
    duration_ms = getattr(preview_variant, "duration_ms", None) or getattr(original_variant, "duration_ms", None)

    return MessageAttachmentGet(
        asset_id=asset.asset_id,
        position=link.sort_order,
        asset_type=asset.asset_type,
        mime_type=mime_type,
        file_kind=_resolve_file_kind(
            mime_type=mime_type,
            filename=getattr(asset, "original_filename", None),
        ),
        original_filename=getattr(asset, "original_filename", None),
        size_bytes=getattr(asset, "size_bytes", None),
        width=width,
        height=height,
        duration_ms=duration_ms,
        preview_url=preview_url,
        original_url=original_url,
        poster_url=await _build_variant_url(storage=storage, variant=poster_variant),
        download_url=download_url,
        stream_url=stream_url,
        is_audio=(mime_type or "").lower().startswith("audio/"),
    )


def build_reply_preview(message: tp.Any) -> MessageReplyPreview:
    deleted = message.deleted_at is not None
    return MessageReplyPreview(
        message_id=message.message_id,
        sender_display_name=message.user.username,
        content_preview=DELETED_MESSAGE_STUB if deleted else message.content_ellipsis,
        deleted=deleted,
    )


def _active_asset_links(message: tp.Any) -> list[tp.Any]:
    return [
        link
        for link in getattr(message, "asset_links", [])
        if getattr(link, "deleted_at", None) is None
    ]


def _pick_variant(asset: tp.Any, variant_type: AssetVariantTypeEnum) -> tp.Any | None:
    for variant in getattr(asset, "variants", []):
        if (
            getattr(variant, "asset_variant_type", None) == variant_type
            and getattr(variant, "status", None) == AssetVariantStatusEnum.READY
        ):
            return variant
    return None


def _pick_preview_variant(asset: tp.Any) -> tp.Any | None:
    variant_order = IMAGE_PREVIEW_VARIANTS if asset.asset_type == AssetTypeEnum.IMAGE else VIDEO_PREVIEW_VARIANTS
    for variant_type in variant_order:
        variant = _pick_variant(asset, variant_type)
        if variant is not None:
            return variant
    return _pick_variant(asset, AssetVariantTypeEnum.ORIGINAL)


def _pick_video_poster_variant(asset: tp.Any) -> tp.Any | None:
    if asset.asset_type != AssetTypeEnum.VIDEO:
        return None
    for variant_type in VIDEO_PREVIEW_VARIANTS:
        variant = _pick_variant(asset, variant_type)
        if variant is not None and getattr(variant, "mime_type", "").startswith("image/"):
            return variant
    return None


async def _build_variant_url(
    *,
    storage: AssetStorage | None,
    variant: tp.Any | None,
) -> str | None:
    if storage is None or variant is None:
        return None
    return await storage.generate_presigned_get(
        bucket=variant.storage_bucket,
        key=variant.storage_key,
    )


async def _build_variant_download_url(
    *,
    storage: AssetStorage | None,
    variant: tp.Any | None,
    filename: str | None,
    mime_type: str | None,
) -> str | None:
    if storage is None or variant is None:
        return None
    return await storage.generate_presigned_get(
        bucket=variant.storage_bucket,
        key=variant.storage_key,
        download_filename=filename,
        inline=False,
        response_content_type=mime_type,
    )


def _resolve_file_kind(
    *,
    mime_type: str | None,
    filename: str | None,
) -> str:
    normalized_mime = (mime_type or "").lower()
    extension = filename.rsplit(".", 1)[1].lower() if filename and "." in filename else ""

    if normalized_mime.startswith("image/"):
        return "image"
    if normalized_mime.startswith("video/"):
        return "video"
    if normalized_mime.startswith("audio/"):
        return "audio"
    if normalized_mime == "application/pdf" or extension == "pdf":
        return "pdf"
    if normalized_mime in {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    } or extension in {"doc", "docx"}:
        return "doc"
    if normalized_mime in {
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
    } or extension in {"xls", "xlsx", "csv"}:
        return "sheet"
    if normalized_mime in {
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    } or extension in {"ppt", "pptx"}:
        return "slides"
    if normalized_mime.startswith("text/") or extension in {"txt", "md"}:
        return "text"
    if normalized_mime in {
        "application/zip",
        "application/x-rar-compressed",
        "application/x-7z-compressed",
    } or extension in {"zip", "rar", "7z"}:
        return "archive"
    return "file"
