from __future__ import annotations

import uuid

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.videos.enums import VideoProcessingStatusEnum


def can_view_content(
    *,
    content,
    viewer_id: uuid.UUID | None,
) -> bool:
    if content.status == ContentStatusEnum.DELETED or content.deleted_at is not None:
        return False

    if (
        content.status == ContentStatusEnum.PUBLISHED
        and content.visibility == ContentVisibilityEnum.PUBLIC
    ):
        return True

    if viewer_id is None or content.author_id != viewer_id:
        return False

    return content.status in {ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT}


def can_access_comments(
    *,
    content,
    viewer_id: uuid.UUID | None,
) -> bool:
    if content.status != ContentStatusEnum.PUBLISHED or not can_view_content(content=content, viewer_id=viewer_id):
        return False
    if getattr(content, "content_type", None) in {ContentTypeEnum.VIDEO, ContentTypeEnum.MOMENT}:
        playback_details = getattr(content, "video_playback_details", None)
        if playback_details is not None:
            return playback_details.processing_status == VideoProcessingStatusEnum.READY
        return getattr(content, "video_processing_status", None) == VideoProcessingStatusEnum.READY
    return True
