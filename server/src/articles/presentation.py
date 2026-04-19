from __future__ import annotations

import typing as tp
import uuid

from src.assets.enums import AssetVariantStatusEnum, AssetVariantTypeEnum, AttachmentTypeEnum
from src.assets.storage import AssetStorage
from src.articles.schemas import ArticleAssetGet, ArticleCardGet, ArticleEditorGet, ArticleGet
from src.users.presentation import build_user_get


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


async def build_article_card_get(
    article: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
) -> ArticleCardGet:
    cover_link = next(
        (
            link for link in getattr(article, "asset_links", [])
            if getattr(link, "deleted_at", None) is None
            and getattr(link, "attachment_type", None) == AttachmentTypeEnum.COVER
        ),
        None,
    )
    cover = await build_article_asset_get(cover_link, storage=storage) if cover_link is not None else None

    return ArticleCardGet(
        article_id=article.content_id,
        content_id=article.content_id,
        title=article.title or "Untitled article",
        excerpt=article.excerpt or "",
        slug=article.article_details.slug,
        canonical_path=f"/articles/{article.content_id}",
        status=article.status,
        visibility=article.visibility,
        created_at=article.created_at,
        updated_at=article.updated_at,
        published_at=article.published_at,
        comments_count=article.comments_count,
        likes_count=article.likes_count,
        dislikes_count=article.dislikes_count,
        reading_time_minutes=article.article_details.reading_time_minutes,
        word_count=article.article_details.word_count,
        user=await build_user_get(article.author, viewer_id=viewer_id, storage=storage),
        tags=article.tags,
        cover=cover,
        my_reaction=article.my_reaction,
        is_owner=article.author_id == viewer_id,
    )


async def build_article_get(
    article: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
) -> ArticleGet:
    card = await build_article_card_get(article, viewer_id=viewer_id, storage=storage)
    referenced_assets: list[ArticleAssetGet] = []

    for link in sorted(
        [
            link for link in getattr(article, "asset_links", [])
            if getattr(link, "deleted_at", None) is None
            and getattr(link, "attachment_type", None) in {AttachmentTypeEnum.INLINE, AttachmentTypeEnum.VIDEO_SOURCE}
        ],
        key=lambda item: (item.attachment_type.value, item.position),
    ):
        asset = await build_article_asset_get(link, storage=storage)
        if asset is not None:
            referenced_assets.append(asset)

    og_image_url = card.cover.preview_url if card.cover is not None else None
    if og_image_url is None:
        first_image = next(
            (asset for asset in referenced_assets if asset.asset_type == "image"),
            None,
        )
        og_image_url = first_image.preview_url if first_image is not None else None

    return ArticleGet(
        **card.model_dump(),
        body_markdown=article.article_details.body_markdown,
        toc=article.article_details.toc,
        referenced_assets=referenced_assets,
        seo_title=article.article_details.seo_title,
        seo_description=article.article_details.seo_description,
        og_image_url=og_image_url,
    )


async def build_article_editor_get(
    article: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
) -> ArticleEditorGet:
    article_get = await build_article_get(article, viewer_id=viewer_id, storage=storage)
    return ArticleEditorGet(
        **article_get.model_dump(),
        slug_editable=article.published_at is None,
    )


async def build_article_asset_get(
    link: tp.Any | None,
    *,
    storage: AssetStorage,
) -> ArticleAssetGet | None:
    if link is None:
        return None

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

    return ArticleAssetGet(
        asset_id=asset.asset_id,
        attachment_type=link.attachment_type.value,
        asset_type=asset.asset_type.value,
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
    variant_order = IMAGE_PREVIEW_VARIANTS if asset.asset_type.value == "image" else VIDEO_PREVIEW_VARIANTS
    for variant_type in variant_order:
        variant = _pick_variant(asset, variant_type)
        if variant is not None:
            return variant
    return _pick_variant(asset, AssetVariantTypeEnum.ORIGINAL)


def _pick_video_poster_variant(asset: tp.Any) -> tp.Any | None:
    if asset.asset_type.value != "video":
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
    if normalized_mime.startswith("text/") or extension in {"txt", "md"}:
        return "text"
    return "file"
