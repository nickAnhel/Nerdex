from __future__ import annotations

import typing as tp
import uuid

from src.assets.enums import AssetTypeEnum, AssetVariantStatusEnum, AssetVariantTypeEnum, AttachmentTypeEnum
from src.assets.schemas import AssetVariantGet
from src.assets.storage import AssetStorage
from src.users.presentation import build_user_get
from src.videos.enums import VideoProcessingStatusEnum
from src.videos.schemas import VideoAssetGet, VideoCardGet, VideoEditorGet, VideoGet, VideoPlaybackSourceGet


IMAGE_PREVIEW_VARIANTS = (
    AssetVariantTypeEnum.IMAGE_SMALL,
    AssetVariantTypeEnum.IMAGE_MEDIUM,
    AssetVariantTypeEnum.ORIGINAL,
)
VIDEO_PLAYBACK_VARIANTS = (
    AssetVariantTypeEnum.ORIGINAL,
    AssetVariantTypeEnum.VIDEO_1080P,
    AssetVariantTypeEnum.VIDEO_720P,
    AssetVariantTypeEnum.VIDEO_480P,
    AssetVariantTypeEnum.VIDEO_360P,
)
VIDEO_GENERATED_PLAYBACK_VARIANTS = (
    AssetVariantTypeEnum.VIDEO_1080P,
    AssetVariantTypeEnum.VIDEO_720P,
    AssetVariantTypeEnum.VIDEO_480P,
    AssetVariantTypeEnum.VIDEO_360P,
)


async def build_video_card_get(
    video: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
) -> VideoCardGet:
    cover_link = _find_link(video, AttachmentTypeEnum.COVER)
    cover = await build_video_asset_get(cover_link, storage=storage) if cover_link is not None else None
    playback = video.video_playback_details
    details = video.video_details
    description = details.description if details is not None else ""

    return VideoCardGet(
        video_id=video.content_id,
        content_id=video.content_id,
        title=video.title or "Untitled video",
        description=description,
        excerpt=video.excerpt or _build_excerpt(description),
        canonical_path=f"/videos/{video.content_id}",
        status=video.status,
        visibility=video.visibility,
        created_at=video.created_at,
        updated_at=video.updated_at,
        published_at=video.published_at,
        comments_count=video.comments_count,
        likes_count=video.likes_count,
        dislikes_count=video.dislikes_count,
        views_count=getattr(video, "views_count", 0),
        duration_seconds=playback.duration_seconds if playback is not None else None,
        orientation=playback.orientation if playback is not None else None,
        processing_status=(
            playback.processing_status
            if playback is not None
            else VideoProcessingStatusEnum.PENDING_UPLOAD
        ),
        processing_error=playback.processing_error if playback is not None else None,
        available_quality_metadata=(
            playback.available_quality_metadata if playback is not None else {}
        ),
        user=await build_user_get(video.author, viewer_id=viewer_id, storage=storage),
        tags=video.tags,
        cover=cover,
        my_reaction=video.my_reaction,
        is_owner=video.author_id == viewer_id,
    )


async def build_video_get(
    video: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
    include_playback_sources: bool,
) -> VideoGet:
    card = await build_video_card_get(video, viewer_id=viewer_id, storage=storage)
    source_link = _find_link(video, AttachmentTypeEnum.VIDEO_SOURCE)
    source_asset = await build_video_asset_get(source_link, storage=storage) if source_link is not None else None
    playback_sources = []
    if include_playback_sources and source_link is not None:
        playback_sources = await build_playback_sources(source_link, storage=storage)

    return VideoGet(
        **card.model_dump(),
        source_asset=source_asset,
        playback_sources=playback_sources,
        chapters=video.video_details.chapters if video.video_details is not None else [],
        publish_requested_at=(
            video.video_details.publish_requested_at if video.video_details is not None else None
        ),
        history_progress=getattr(video, "history_progress", None),
    )


async def build_video_editor_get(
    video: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
) -> VideoEditorGet:
    video_get = await build_video_get(
        video,
        viewer_id=viewer_id,
        storage=storage,
        include_playback_sources=(
            video.video_playback_details is not None
            and video.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
        ),
    )
    source_link = _find_link(video, AttachmentTypeEnum.VIDEO_SOURCE)
    cover_link = _find_link(video, AttachmentTypeEnum.COVER)
    return VideoEditorGet(
        **video_get.model_dump(),
        source_asset_id=getattr(source_link, "asset_id", None),
        cover_asset_id=getattr(cover_link, "asset_id", None),
    )


async def build_video_asset_get(
    link: tp.Any | None,
    *,
    storage: AssetStorage,
) -> VideoAssetGet | None:
    if link is None:
        return None
    asset = getattr(link, "asset", None)
    if asset is None:
        return None

    original_variant = _pick_variant(asset, AssetVariantTypeEnum.ORIGINAL)
    preview_variant = _pick_image_preview_variant(asset)
    mime_type = getattr(asset, "detected_mime_type", None) or getattr(original_variant, "mime_type", None)
    original_url = await _build_variant_url(storage=storage, variant=original_variant)
    preview_url = await _build_variant_url(storage=storage, variant=preview_variant)
    if preview_url is None:
        preview_url = original_url
    variants = [
        await _build_asset_variant_get(storage=storage, variant=variant)
        for variant in sorted(getattr(asset, "variants", []), key=lambda item: item.created_at)
    ]

    return VideoAssetGet(
        asset_id=asset.asset_id,
        attachment_type=link.attachment_type,
        asset_type=asset.asset_type,
        status=asset.status,
        mime_type=mime_type,
        original_filename=getattr(asset, "original_filename", None),
        size_bytes=getattr(asset, "size_bytes", None),
        width=getattr(preview_variant, "width", None) or getattr(original_variant, "width", None),
        height=getattr(preview_variant, "height", None) or getattr(original_variant, "height", None),
        duration_ms=getattr(original_variant, "duration_ms", None),
        preview_url=preview_url,
        original_url=original_url,
        poster_url=preview_url,
        variants=variants,
    )


async def _build_asset_variant_get(
    *,
    storage: AssetStorage,
    variant: tp.Any,
) -> AssetVariantGet:
    url = None
    if getattr(variant, "status", None) == AssetVariantStatusEnum.READY:
        url = await _build_variant_url(storage=storage, variant=variant)
    return AssetVariantGet(
        asset_variant_type=variant.asset_variant_type,
        mime_type=variant.mime_type,
        size_bytes=variant.size_bytes,
        width=variant.width,
        height=variant.height,
        duration_ms=variant.duration_ms,
        status=variant.status,
        url=url,
    )


async def build_playback_sources(
    link: tp.Any,
    *,
    storage: AssetStorage,
) -> list[VideoPlaybackSourceGet]:
    asset = getattr(link, "asset", None)
    if asset is None:
        return []

    sources: list[VideoPlaybackSourceGet] = []
    for variant_type in VIDEO_PLAYBACK_VARIANTS:
        variant = _pick_variant(asset, variant_type)
        if variant is None:
            continue
        if variant_type == AssetVariantTypeEnum.ORIGINAL and not _is_browser_playable_original(asset, variant):
            continue
        url = await _build_variant_url(storage=storage, variant=variant)
        if url is None:
            continue
        sources.append(
            VideoPlaybackSourceGet(
                id=_playback_source_id(variant_type),
                label=_playback_source_label(variant_type),
                src=url,
                mimeType=variant.mime_type,
                width=variant.width,
                height=variant.height,
                bitrate=variant.bitrate,
                isOriginal=variant_type == AssetVariantTypeEnum.ORIGINAL,
            )
        )

    generated = [source for source in sources if not source.isOriginal]
    originals = [source for source in sources if source.isOriginal]
    return generated + originals


def _find_link(video: tp.Any, attachment_type: AttachmentTypeEnum) -> tp.Any | None:
    return next(
        (
            link
            for link in getattr(video, "asset_links", [])
            if getattr(link, "deleted_at", None) is None
            and getattr(link, "attachment_type", None) == attachment_type
        ),
        None,
    )


def _pick_variant(asset: tp.Any, variant_type: AssetVariantTypeEnum) -> tp.Any | None:
    for variant in getattr(asset, "variants", []):
        if (
            getattr(variant, "asset_variant_type", None) == variant_type
            and getattr(variant, "status", None) == AssetVariantStatusEnum.READY
        ):
            return variant
    return None


def _pick_image_preview_variant(asset: tp.Any) -> tp.Any | None:
    if getattr(asset, "asset_type", None) != AssetTypeEnum.IMAGE:
        return _pick_variant(asset, AssetVariantTypeEnum.ORIGINAL)
    for variant_type in IMAGE_PREVIEW_VARIANTS:
        variant = _pick_variant(asset, variant_type)
        if variant is not None:
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


def _is_browser_playable_original(asset: tp.Any, variant: tp.Any) -> bool:
    mime_type = (getattr(variant, "mime_type", None) or getattr(asset, "detected_mime_type", "") or "").lower()
    extension = (getattr(asset, "original_extension", "") or "").lower()
    if extension == "mov" or mime_type in {"video/quicktime", "video/x-quicktime"}:
        return False
    return mime_type in {"video/mp4", "video/webm"}


def _playback_source_id(variant_type: AssetVariantTypeEnum) -> str:
    mapping = {
        AssetVariantTypeEnum.ORIGINAL: "original",
        AssetVariantTypeEnum.VIDEO_1080P: "1080p",
        AssetVariantTypeEnum.VIDEO_720P: "720p",
        AssetVariantTypeEnum.VIDEO_480P: "480p",
        AssetVariantTypeEnum.VIDEO_360P: "360p",
    }
    return mapping[variant_type]


def _playback_source_label(variant_type: AssetVariantTypeEnum) -> str:
    mapping = {
        AssetVariantTypeEnum.ORIGINAL: "Original",
        AssetVariantTypeEnum.VIDEO_1080P: "1080p",
        AssetVariantTypeEnum.VIDEO_720P: "720p",
        AssetVariantTypeEnum.VIDEO_480P: "480p",
        AssetVariantTypeEnum.VIDEO_360P: "360p",
    }
    return mapping[variant_type]


def _build_excerpt(description: str) -> str:
    text = " ".join(description.split())
    if len(text) <= 220:
        return text
    return text[:217].rstrip() + "..."
