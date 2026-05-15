from __future__ import annotations

import datetime as dt
import uuid

from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.demo_seed.generators.messages import build_messages
from src.demo_seed.planning.plans import PlannedChat, PlannedContent, PlannedMembership, PlannedUser
from src.demo_seed.planning.random_state import SeedRandom
from src.demo_seed.planning.time_distribution import TimeDistributor
from src.videos.enums import VideoProcessingStatusEnum


def _user(index: int) -> PlannedUser:
    return PlannedUser(
        user_id=uuid.uuid4(),
        username=f"user_{index}",
        display_name=f"User {index}",
        hashed_password="hash",
        bio="bio",
        links=[],
        is_admin=False,
        created_at=dt.datetime.now(dt.timezone.utc),
        interests={"backend": 1.0},
        preferred_content_types={"post": 1.0},
        expected_tags=["fastapi"],
        role="regular_user",
        is_featured=False,
        presentation_note_en="note",
    )


def _content(
    *,
    status: ContentStatusEnum,
    visibility: ContentVisibilityEnum,
    content_type: ContentTypeEnum = ContentTypeEnum.POST,
    playback_status: VideoProcessingStatusEnum | None = None,
) -> PlannedContent:
    now = dt.datetime.now(dt.timezone.utc)
    return PlannedContent(
        content_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        content_type=content_type,
        status=status,
        visibility=visibility,
        title="t",
        excerpt="e",
        created_at=now,
        updated_at=now,
        published_at=now if status == ContentStatusEnum.PUBLISHED else None,
        content_metadata={},
        topic="backend",
        tags=[],
        media_asset_ids=[],
        cover_asset_id=None,
        file_asset_ids=[],
        playback_status=playback_status,
    )


def test_messages_share_only_public_published_content() -> None:
    left = _user(1)
    right = _user(2)
    chat = PlannedChat(
        chat_id=uuid.uuid4(),
        owner_id=left.user_id,
        title="Demo chat",
        chat_type="direct",
        is_private=True,
        direct_key=f"{left.user_id}:{right.user_id}",
    )
    memberships = [
        PlannedMembership(chat_id=chat.chat_id, user_id=left.user_id, role="owner"),
        PlannedMembership(chat_id=chat.chat_id, user_id=right.user_id, role="member"),
    ]

    allowed_post = _content(
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        content_type=ContentTypeEnum.POST,
    )
    forbidden_private = _content(
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        content_type=ContentTypeEnum.POST,
    )
    forbidden_draft = _content(
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        content_type=ContentTypeEnum.POST,
    )
    forbidden_video_not_ready = _content(
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        content_type=ContentTypeEnum.VIDEO,
        playback_status=VideoProcessingStatusEnum.PENDING_UPLOAD,
    )

    plan = build_messages(
        random=SeedRandom(7),
        distributor=TimeDistributor(SeedRandom(7)),
        chats=[chat],
        memberships=memberships,
        contents=[
            allowed_post,
            forbidden_private,
            forbidden_draft,
            forbidden_video_not_ready,
        ],
        file_asset_ids=[],
        min_count=200,
        max_count=200,
        reactions_min=0,
        reactions_max=0,
        initial_seq_by_chat={chat.chat_id: 1},
    )

    shared_content_ids = {item.content_id for item in plan.shared_content}
    assert shared_content_ids <= {allowed_post.content_id}
