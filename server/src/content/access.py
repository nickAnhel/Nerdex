from __future__ import annotations

import uuid

from src.content.enums import ContentStatusEnum, ContentVisibilityEnum


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
    return (
        content.status == ContentStatusEnum.PUBLISHED
        and can_view_content(content=content, viewer_id=viewer_id)
    )
