from __future__ import annotations

import typing as tp
import uuid

from src.assets.enums import AttachmentTypeEnum
from src.assets.storage import AssetStorage
from src.moments.schemas import MomentEditorGet, MomentGet
from src.users.presentation import build_user_get
from src.videos.enums import VideoProcessingStatusEnum
from src.videos.presentation import build_playback_sources, build_video_asset_get


async def build_moment_get(
    moment: tp.Any,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
    include_playback_sources: bool,
) -> MomentGet:
    cover_link = _find_link(moment, AttachmentTypeEnum.COVER)
    source_link = _find_link(moment, AttachmentTypeEnum.VIDEO_SOURCE)
    cover = await build_video_asset_get(cover_link, storage=storage) if cover_link is not None else None
    source_asset = await build_video_asset_get(source_link, storage=storage) if source_link is not None else None
    playback_sources = []
    if include_playback_sources and source_link is not None:
        playback_sources = await build_playback_sources(source_link, storage=storage)

    playback = moment.video_playback_details
    details = moment.moment_details
    return MomentGet(
        moment_id=moment.content_id,
        content_id=moment.content_id,
        status=moment.status,
        visibility=moment.visibility,
        caption=details.caption if details is not None else "",
        created_at=moment.created_at,
        updated_at=moment.updated_at,
        published_at=moment.published_at,
        publish_requested_at=details.publish_requested_at if details is not None else None,
        comments_count=moment.comments_count,
        likes_count=moment.likes_count,
        dislikes_count=moment.dislikes_count,
        views_count=getattr(moment, "views_count", 0),
        duration_seconds=playback.duration_seconds if playback is not None else None,
        width=playback.width if playback is not None else None,
        height=playback.height if playback is not None else None,
        orientation=playback.orientation if playback is not None else None,
        processing_status=(
            playback.processing_status
            if playback is not None
            else VideoProcessingStatusEnum.PENDING_UPLOAD
        ),
        processing_error=playback.processing_error if playback is not None else None,
        available_quality_metadata=playback.available_quality_metadata if playback is not None else {},
        user=await build_user_get(moment.author, viewer_id=viewer_id, storage=storage),
        tags=moment.tags,
        cover=cover,
        source_asset=source_asset,
        playback_sources=playback_sources,
        my_reaction=moment.my_reaction,
        is_owner=moment.author_id == viewer_id,
    )


async def build_moment_editor_get(
    moment: tp.Any,
    *,
    viewer_id: uuid.UUID,
    storage: AssetStorage,
) -> MomentEditorGet:
    moment_get = await build_moment_get(
        moment,
        viewer_id=viewer_id,
        storage=storage,
        include_playback_sources=(
            moment.video_playback_details is not None
            and moment.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
        ),
    )
    source_link = _find_link(moment, AttachmentTypeEnum.VIDEO_SOURCE)
    cover_link = _find_link(moment, AttachmentTypeEnum.COVER)
    return MomentEditorGet(
        **moment_get.model_dump(),
        source_asset_id=getattr(source_link, "asset_id", None),
        cover_asset_id=getattr(cover_link, "asset_id", None),
    )


def _find_link(moment: tp.Any, attachment_type: AttachmentTypeEnum) -> tp.Any | None:
    return next(
        (
            link
            for link in getattr(moment, "asset_links", [])
            if getattr(link, "deleted_at", None) is None
            and getattr(link, "attachment_type", None) == attachment_type
        ),
        None,
    )
