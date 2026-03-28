from __future__ import annotations

import typing as tp
import uuid

from src.assets.enums import AttachmentTypeEnum, AssetTypeEnum, AssetVariantStatusEnum, AssetVariantTypeEnum
from src.assets.storage import AssetStorage
from src.posts.schemas import PostAttachmentGet, PostGet
from src.users.presentation import build_user_get


MEDIA_ATTACHMENT_TYPES = {
    AttachmentTypeEnum.MEDIA,
    AttachmentTypeEnum.FILE,
}

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


async def build_post_get(
    post: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
) -> PostGet:
    media_attachments: list[PostAttachmentGet] = []
    file_attachments: list[PostAttachmentGet] = []

    sorted_links = sorted(
        [
            link
            for link in getattr(post, "asset_links", [])
            if getattr(link, "deleted_at", None) is None
            and getattr(link, "attachment_type", None) in MEDIA_ATTACHMENT_TYPES
        ],
        key=lambda link: (
            0 if link.attachment_type == AttachmentTypeEnum.MEDIA else 1,
            link.position,
        ),
    )
    for link in sorted_links:
        attachment = await build_post_attachment_get(link, storage=storage)
        if attachment is None:
            continue
        if attachment.attachment_type == AttachmentTypeEnum.MEDIA:
            media_attachments.append(attachment)
        else:
            file_attachments.append(attachment)

    return PostGet(
        post_id=post.content_id,
        user_id=post.author_id,
        content=post.post_details.body_text,
        status=post.status,
        visibility=post.visibility,
        created_at=post.created_at,
        updated_at=post.updated_at,
        published_at=post.published_at,
        deleted_at=post.deleted_at,
        comments_count=post.comments_count,
        likes_count=post.likes_count,
        dislikes_count=post.dislikes_count,
        user=await build_user_get(post.author, viewer_id=viewer_id, storage=storage),
        tags=post.tags,
        media_attachments=media_attachments,
        file_attachments=file_attachments,
        my_reaction=post.my_reaction,
        is_owner=post.author_id == viewer_id,
    )


async def build_post_attachment_get(
    link: tp.Any,
    *,
    storage: AssetStorage,
) -> PostAttachmentGet | None:
    asset = getattr(link, "asset", None)
    if asset is None:
        return None

    original_variant = _pick_variant(asset, AssetVariantTypeEnum.ORIGINAL)
    preview_variant = _pick_preview_variant(asset)
    poster_variant = _pick_video_poster_variant(asset)

    mime_type = getattr(asset, "detected_mime_type", None) or getattr(original_variant, "mime_type", None)
    original_url = await _build_variant_url(storage=storage, variant=original_variant)
    preview_url = await _build_variant_url(storage=storage, variant=preview_variant)
    if preview_url is None:
        preview_url = original_url

    download_url = None
    stream_url = None
    if original_variant is not None:
        stream_url = await _build_variant_url(storage=storage, variant=original_variant)
        download_url = await _build_variant_download_url(
            storage=storage,
            variant=original_variant,
            filename=getattr(asset, "original_filename", None),
            mime_type=mime_type,
        )

    width = getattr(preview_variant, "width", None) or getattr(original_variant, "width", None)
    height = getattr(preview_variant, "height", None) or getattr(original_variant, "height", None)
    duration_ms = getattr(preview_variant, "duration_ms", None) or getattr(original_variant, "duration_ms", None)
    poster_url = await _build_variant_url(storage=storage, variant=poster_variant)

    return PostAttachmentGet(
        asset_id=asset.asset_id,
        attachment_type=link.attachment_type,
        position=link.position,
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
        poster_url=poster_url,
        download_url=download_url,
        stream_url=stream_url,
        is_audio=_is_audio_mime_type(mime_type),
    )


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
    storage: AssetStorage,
    variant: tp.Any | None,
) -> str | None:
    if variant is None:
        return None
    return await storage.generate_presigned_get(
        bucket=variant.storage_bucket,
        key=variant.storage_key,
    )


async def _build_variant_download_url(
    *,
    storage: AssetStorage,
    variant: tp.Any | None,
    filename: str | None,
    mime_type: str | None,
) -> str | None:
    if variant is None:
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
    extension = ""
    if filename and "." in filename:
        extension = filename.rsplit(".", 1)[1].lower()

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


def _is_audio_mime_type(mime_type: str | None) -> bool:
    return (mime_type or "").lower().startswith("audio/")
