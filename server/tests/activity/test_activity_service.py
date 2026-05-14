import datetime
import uuid

import pytest

from src.activity.enums import ActivityActionTypeEnum
from src.activity.service import ActivityService, COMMENT_PREVIEW_MAX_LENGTH
from src.comments.repository import CommentState
from src.content.enums import ContentTypeEnum, ReactionTypeEnum


class FakeActivityRepository:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.rollback_calls = 0

    async def create_event(self, **kwargs):  # type: ignore[no-untyped-def]
        self.events.append(kwargs)
        return kwargs

    async def rollback(self) -> None:
        self.rollback_calls += 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_log_content_view_creates_event() -> None:
    repository = FakeActivityRepository()
    service = ActivityService(repository=repository, asset_storage=None, projector_registry=None)  # type: ignore[arg-type]
    user_id = uuid.uuid4()
    content_id = uuid.uuid4()
    session_id = uuid.uuid4()

    await service.log_content_view(
        user_id=user_id,
        content_id=content_id,
        content_type=ContentTypeEnum.ARTICLE,
        view_session_id=session_id,
        source="article_detail",
        progress_percent=30,
        watched_seconds=10,
    )

    assert repository.events[0]["action_type"] == ActivityActionTypeEnum.CONTENT_VIEW
    assert repository.events[0]["metadata"]["view_session_id"] == str(session_id)
    assert repository.events[0]["metadata"]["progress_percent"] == 30


@pytest.mark.anyio
async def test_log_content_reactions_and_removed_reaction() -> None:
    repository = FakeActivityRepository()
    service = ActivityService(repository=repository, asset_storage=None, projector_registry=None)  # type: ignore[arg-type]
    user_id = uuid.uuid4()
    content_id = uuid.uuid4()

    await service.log_content_reaction(
        user_id=user_id,
        content_id=content_id,
        content_type=ContentTypeEnum.POST,
        previous_reaction=None,
        new_reaction=ReactionTypeEnum.LIKE,
    )
    await service.log_content_reaction(
        user_id=user_id,
        content_id=content_id,
        content_type=ContentTypeEnum.POST,
        previous_reaction=ReactionTypeEnum.LIKE,
        new_reaction=ReactionTypeEnum.DISLIKE,
    )
    await service.log_content_reaction_removed(
        user_id=user_id,
        content_id=content_id,
        content_type=ContentTypeEnum.POST,
        previous_reaction=ReactionTypeEnum.DISLIKE,
    )

    assert [event["action_type"] for event in repository.events] == [
        ActivityActionTypeEnum.CONTENT_LIKE,
        ActivityActionTypeEnum.CONTENT_DISLIKE,
        ActivityActionTypeEnum.CONTENT_REACTION_REMOVED,
    ]
    assert repository.events[-1]["metadata"] == {"previous_reaction": "dislike"}


@pytest.mark.anyio
async def test_log_comment_limits_preview() -> None:
    repository = FakeActivityRepository()
    service = ActivityService(repository=repository, asset_storage=None, projector_registry=None)  # type: ignore[arg-type]
    long_body = "x" * 300
    comment = CommentState(
        comment_id=uuid.uuid4(),
        content_id=uuid.uuid4(),
        author_id=uuid.uuid4(),
        parent_comment_id=None,
        root_comment_id=None,
        reply_to_comment_id=None,
        depth=0,
        body_text=long_body,
        replies_count=0,
        likes_count=0,
        dislikes_count=0,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
        deleted_at=None,
    )

    await service.log_content_comment(
        user_id=comment.author_id,
        content_id=comment.content_id,
        content_type=ContentTypeEnum.POST,
        comment=comment,
    )

    preview = repository.events[0]["metadata"]["comment_preview"]
    assert len(preview) == COMMENT_PREVIEW_MAX_LENGTH
    assert preview.endswith("...")


@pytest.mark.anyio
async def test_log_follow_and_unfollow_target_user() -> None:
    repository = FakeActivityRepository()
    service = ActivityService(repository=repository, asset_storage=None, projector_registry=None)  # type: ignore[arg-type]
    user_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    await service.log_user_follow(user_id=user_id, target_user_id=target_user_id)
    await service.log_user_unfollow(user_id=user_id, target_user_id=target_user_id)

    assert [event["action_type"] for event in repository.events] == [
        ActivityActionTypeEnum.USER_FOLLOW,
        ActivityActionTypeEnum.USER_UNFOLLOW,
    ]
    assert repository.events[0]["target_user_id"] == target_user_id
