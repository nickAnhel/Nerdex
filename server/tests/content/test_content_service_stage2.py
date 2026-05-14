import datetime
import uuid
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from src.assets.enums import AssetTypeEnum, AttachmentTypeEnum
from src.content.enums import (
    ContentProfileFilterEnum,
    ContentStatusEnum,
    ContentTypeEnum,
    ContentVisibilityEnum,
    ReactionTypeEnum,
)
from src.content.enums_list import ContentOrder
from src.content.exceptions import ContentNotFound
from src.content.repository import ContentReactionRemoveResult, ContentReactionSetResult
from src.content.schemas import ContentListItemGet, ContentViewSessionHeartbeat, ContentViewSessionStart
from src.content.service import ContentService
from src.posts.schemas import PostAttachmentGet
from src.users.schemas import UserGet
from src.videos.enums import VideoProcessingStatusEnum


@dataclass
class FakePlayback:
    processing_status: VideoProcessingStatusEnum = VideoProcessingStatusEnum.READY
    duration_seconds: int | None = 100


@dataclass
class FakePostDetails:
    body_text: str = ""


@dataclass
class FakeAsset:
    asset_id: uuid.UUID = field(default_factory=uuid.uuid4)
    asset_type: AssetTypeEnum = AssetTypeEnum.IMAGE
    detected_mime_type: str | None = "image/jpeg"
    original_filename: str | None = "image.jpg"
    size_bytes: int | None = 128
    variants: list = field(default_factory=list)


@dataclass
class FakeLink:
    attachment_type: AttachmentTypeEnum = AttachmentTypeEnum.MEDIA
    position: int = 0
    asset: FakeAsset = field(default_factory=FakeAsset)
    deleted_at: datetime.datetime | None = None


@dataclass
class FakeContent:
    content_id: uuid.UUID
    author_id: uuid.UUID
    author: UserGet
    content_type: ContentTypeEnum = ContentTypeEnum.VIDEO
    status: ContentStatusEnum = ContentStatusEnum.PUBLISHED
    visibility: ContentVisibilityEnum = ContentVisibilityEnum.PUBLIC
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    published_at: datetime.datetime | None = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    deleted_at: datetime.datetime | None = None
    comments_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    views_count: int = 0
    video_playback_details: FakePlayback | None = field(default_factory=FakePlayback)
    post_details: FakePostDetails | None = field(default_factory=FakePostDetails)
    asset_links: list[FakeLink] = field(default_factory=list)
    tags: list = field(default_factory=list)
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool = False


@dataclass
class FakeSession:
    view_session_id: uuid.UUID
    content_id: uuid.UUID
    viewer_id: uuid.UUID
    started_at: datetime.datetime
    last_seen_at: datetime.datetime
    last_position_seconds: int
    max_position_seconds: int
    watched_seconds: int = 0
    progress_percent: int = 0
    is_counted: bool = False
    counted_at: datetime.datetime | None = None
    counted_date: datetime.date | None = None
    source: str | None = None
    view_metadata: dict = field(default_factory=dict)


class FakeRepository:
    def __init__(self, content: FakeContent) -> None:
        self.content = content
        self.reactions: dict[tuple[uuid.UUID, uuid.UUID], ReactionTypeEnum] = {}
        self.sessions: dict[uuid.UUID, FakeSession] = {}
        self.publications: list[FakeContent] = [content]
        self.gallery_posts: list[FakeContent] = [content]

    async def get_single(self, *, content_id: uuid.UUID, viewer_id: uuid.UUID | None = None):
        if content_id != self.content.content_id:
            return None
        self.content.my_reaction = self.reactions.get((content_id, viewer_id)) if viewer_id else None
        self.content.is_owner = self.content.author_id == viewer_id
        return self.content

    async def set_reaction(self, *, content_id: uuid.UUID, user_id: uuid.UUID, reaction_type: ReactionTypeEnum) -> ContentReactionSetResult:
        existing = self.reactions.get((content_id, user_id))
        if existing == reaction_type:
            return ContentReactionSetResult(changed=False, previous_reaction=existing, new_reaction=reaction_type)
        if existing == ReactionTypeEnum.LIKE:
            self.content.likes_count -= 1
        elif existing == ReactionTypeEnum.DISLIKE:
            self.content.dislikes_count -= 1
        if reaction_type == ReactionTypeEnum.LIKE:
            self.content.likes_count += 1
        else:
            self.content.dislikes_count += 1
        self.reactions[(content_id, user_id)] = reaction_type
        return ContentReactionSetResult(changed=True, previous_reaction=existing, new_reaction=reaction_type)

    async def remove_reaction(self, *, content_id: uuid.UUID, user_id: uuid.UUID, reaction_type: ReactionTypeEnum | None = None) -> ContentReactionRemoveResult:
        existing = self.reactions.get((content_id, user_id))
        if existing is None or (reaction_type is not None and existing != reaction_type):
            return ContentReactionRemoveResult(removed=False, previous_reaction=existing)
        if existing == ReactionTypeEnum.LIKE:
            self.content.likes_count -= 1
        else:
            self.content.dislikes_count -= 1
        del self.reactions[(content_id, user_id)]
        return ContentReactionRemoveResult(removed=True, previous_reaction=existing)

    async def create_view_session(  # type: ignore[no-untyped-def]
        self,
        *,
        content_id,
        viewer_id,
        started_at,
        last_position_seconds,
        max_position_seconds,
        watched_seconds,
        progress_percent,
        last_seen_at=None,
        is_counted=False,
        counted_at=None,
        counted_date=None,
        increment_views=False,
        source,
        metadata,
    ):
        session = FakeSession(
            view_session_id=uuid.uuid4(),
            content_id=content_id,
            viewer_id=viewer_id,
            started_at=started_at,
            last_seen_at=last_seen_at or started_at,
            last_position_seconds=last_position_seconds,
            max_position_seconds=max_position_seconds,
            watched_seconds=watched_seconds,
            progress_percent=progress_percent,
            is_counted=is_counted,
            counted_at=counted_at,
            counted_date=counted_date,
            source=source,
            view_metadata=metadata,
        )
        self.sessions[session.view_session_id] = session
        if increment_views:
            self.content.views_count += 1
        return session

    async def get_view_session(self, *, view_session_id, content_id, viewer_id):  # type: ignore[no-untyped-def]
        session = self.sessions.get(view_session_id)
        if session and session.content_id == content_id and session.viewer_id == viewer_id:
            return session
        return None

    async def get_latest_view_session(self, *, content_id, viewer_id):  # type: ignore[no-untyped-def]
        matches = [session for session in self.sessions.values() if session.content_id == content_id and session.viewer_id == viewer_id]
        return max(matches, key=lambda session: session.last_seen_at, default=None)

    async def update_view_session(self, *, view_session_id, increment_views, content_id, **values):  # type: ignore[no-untyped-def]
        session = self.sessions[view_session_id]
        for key, value in values.items():
            setattr(session, key, value)
        if increment_views:
            self.content.views_count += 1
        return self.content.views_count

    async def has_counted_view_on_date(self, *, content_id, viewer_id, counted_date):  # type: ignore[no-untyped-def]
        return any(
            session.content_id == content_id
            and session.viewer_id == viewer_id
            and session.counted_date == counted_date
            and session.is_counted
            for session in self.sessions.values()
        )

    async def get_views_count(self, *, content_id):  # type: ignore[no-untyped-def]
        return self.content.views_count

    async def get_history_sessions(self, *, viewer_id, content_type=None, offset, limit):  # type: ignore[no-untyped-def]
        return [(self.content, session) for session in list(self.sessions.values())[offset:offset + limit] if session.viewer_id == viewer_id]

    async def get_author_publications(self, **kwargs):  # type: ignore[no-untyped-def]
        viewer_id = kwargs["viewer_id"]
        author_id = kwargs["author_id"]
        content_type = kwargs["content_type"]
        profile_filter = kwargs["profile_filter"]

        items = self.publications
        if content_type is not None:
            items = [item for item in items if item.content_type == content_type]

        if viewer_id == author_id:
            if profile_filter == ContentProfileFilterEnum.DRAFTS:
                return [item for item in items if item.status == ContentStatusEnum.DRAFT]
            if profile_filter == ContentProfileFilterEnum.PRIVATE:
                return [
                    item
                    for item in items
                    if item.status == ContentStatusEnum.PUBLISHED
                    and item.visibility == ContentVisibilityEnum.PRIVATE
                ]
            if profile_filter == ContentProfileFilterEnum.PUBLIC:
                return [
                    item
                    for item in items
                    if item.status == ContentStatusEnum.PUBLISHED
                    and item.visibility == ContentVisibilityEnum.PUBLIC
                ]
            return [
                item
                for item in items
                if item.status in {ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT}
            ]

        return [
            item
            for item in items
            if item.status == ContentStatusEnum.PUBLISHED
            and item.visibility == ContentVisibilityEnum.PUBLIC
        ]

    async def get_author_gallery_posts(self, **kwargs):  # type: ignore[no-untyped-def]
        viewer_id = kwargs["viewer_id"]
        author_id = kwargs["author_id"]
        profile_filter = kwargs["profile_filter"]
        items = self.gallery_posts

        if viewer_id == author_id:
            if profile_filter == ContentProfileFilterEnum.DRAFTS:
                return [item for item in items if item.status == ContentStatusEnum.DRAFT]
            if profile_filter == ContentProfileFilterEnum.PRIVATE:
                return [
                    item
                    for item in items
                    if item.status == ContentStatusEnum.PUBLISHED
                    and item.visibility == ContentVisibilityEnum.PRIVATE
                ]
            if profile_filter == ContentProfileFilterEnum.PUBLIC:
                return [
                    item
                    for item in items
                    if item.status == ContentStatusEnum.PUBLISHED
                    and item.visibility == ContentVisibilityEnum.PUBLIC
                ]
            return [
                item
                for item in items
                if item.status in {ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT}
            ]

        return [
            item
            for item in items
            if item.status == ContentStatusEnum.PUBLISHED
            and item.visibility == ContentVisibilityEnum.PUBLIC
        ]


class FakeProjectorRegistry:
    def get(self, content_type):  # type: ignore[no-untyped-def]
        return self

    async def project_feed_item(self, item, *, viewer_id, storage):  # type: ignore[no-untyped-def]
        return ContentListItemGet(
            content_id=item.content_id,
            content_type=item.content_type,
            status=item.status,
            visibility=item.visibility,
            created_at=item.created_at,
            updated_at=item.updated_at,
            published_at=item.published_at,
            comments_count=item.comments_count,
            likes_count=item.likes_count,
            dislikes_count=item.dislikes_count,
            views_count=item.views_count,
            user=item.author,
            tags=[],
            my_reaction=item.my_reaction,
            is_owner=item.author_id == viewer_id,
        )


class FakeActivityService:
    def __init__(self) -> None:
        self.content_views: list[dict] = []
        self.reactions: list[dict] = []
        self.removed_reactions: list[dict] = []

    async def log_content_view(self, **kwargs):  # type: ignore[no-untyped-def]
        self.content_views.append(kwargs)

    async def log_content_reaction(self, **kwargs):  # type: ignore[no-untyped-def]
        self.reactions.append(kwargs)

    async def log_content_reaction_removed(self, **kwargs):  # type: ignore[no-untyped-def]
        self.removed_reactions.append(kwargs)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_user(username: str) -> UserGet:
    return UserGet(
        user_id=uuid.uuid4(),
        username=username,
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
        is_subscribed=False,
    )


@pytest.fixture
def service_bundle():
    author = make_user("author")
    viewer = make_user("viewer")
    content = FakeContent(content_id=uuid.uuid4(), author_id=author.user_id, author=author)
    repository = FakeRepository(content)
    activity = FakeActivityService()
    service = ContentService(
        repository=repository,
        asset_storage=None,
        projector_registry=FakeProjectorRegistry(),
        activity_service=activity,
    )  # type: ignore[arg-type]
    return service, repository, content, author, viewer


@pytest.mark.anyio
async def test_generic_content_reaction_switches_and_removes(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    activity = service._activity_service

    liked = await service.set_reaction(content_id=content.content_id, user=viewer, reaction_type=ReactionTypeEnum.LIKE)
    disliked = await service.set_reaction(content_id=content.content_id, user=viewer, reaction_type=ReactionTypeEnum.DISLIKE)
    removed = await service.remove_reaction(content_id=content.content_id, user=viewer)

    assert liked.likes_count == 1
    assert disliked.likes_count == 0
    assert disliked.dislikes_count == 1
    assert removed.dislikes_count == 0
    assert removed.my_reaction is None
    assert [event["new_reaction"] for event in activity.reactions] == [
        ReactionTypeEnum.LIKE,
        ReactionTypeEnum.DISLIKE,
    ]
    assert activity.removed_reactions[0]["previous_reaction"] == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_generic_content_reaction_no_op_does_not_log_activity(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    activity = service._activity_service

    await service.set_reaction(content_id=content.content_id, user=viewer, reaction_type=ReactionTypeEnum.LIKE)
    await service.set_reaction(content_id=content.content_id, user=viewer, reaction_type=ReactionTypeEnum.LIKE)
    await service.remove_reaction(content_id=content.content_id, user=viewer, reaction_type=ReactionTypeEnum.DISLIKE)

    assert len(activity.reactions) == 1
    assert activity.removed_reactions == []


@pytest.mark.anyio
async def test_processing_video_does_not_accept_generic_reaction(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    content.video_playback_details.processing_status = VideoProcessingStatusEnum.TRANSCODING

    with pytest.raises(ContentNotFound):
        await service.set_reaction(content_id=content.content_id, user=viewer, reaction_type=ReactionTypeEnum.LIKE)


@pytest.mark.anyio
async def test_post_view_session_counts_on_start_once_per_day(service_bundle) -> None:
    service, repository, content, _author, viewer = service_bundle
    activity = service._activity_service
    content.content_type = ContentTypeEnum.POST
    content.video_playback_details = None

    first = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="post_detail", initial_progress_percent=100),
    )
    second = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="post_detail", initial_progress_percent=100),
    )

    assert first.is_counted is True
    assert first.progress_percent == 100
    assert first.views_count == 1
    assert second.is_counted is False
    assert second.views_count == 1
    assert content.views_count == 1
    assert len(repository.sessions) == 2
    assert len(activity.content_views) == 1
    assert activity.content_views[0]["view_session_id"] == first.view_session_id


@pytest.mark.anyio
async def test_article_start_persists_restored_latest_progress(service_bundle) -> None:
    service, repository, content, _author, viewer = service_bundle
    content.content_type = ContentTypeEnum.ARTICLE
    content.video_playback_details = None

    first = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="article_detail", initial_progress_percent=40),
    )
    repository.sessions[first.view_session_id].watched_seconds = 6
    second = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="article_detail", initial_progress_percent=15),
    )
    persisted = repository.sessions[second.view_session_id]

    assert second.progress_percent == 40
    assert persisted.progress_percent == 40
    assert persisted.watched_seconds == 6


@pytest.mark.anyio
async def test_article_heartbeat_accepts_missing_position_and_keeps_progress_monotonic(service_bundle) -> None:
    service, repository, content, _author, viewer = service_bundle
    content.content_type = ContentTypeEnum.ARTICLE
    content.video_playback_details = None

    started = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="article_detail", initial_progress_percent=20),
    )
    updated = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(progress_percent=15, watched_seconds_delta=3),
    )
    persisted = repository.sessions[started.view_session_id]

    assert updated.progress_percent == 20
    assert updated.watched_seconds == 3
    assert persisted.last_position_seconds == 0
    assert persisted.max_position_seconds == 0


@pytest.mark.anyio
async def test_article_view_session_counts_at_progress_threshold(service_bundle) -> None:
    service, repository, content, _author, viewer = service_bundle
    activity = service._activity_service
    content.content_type = ContentTypeEnum.ARTICLE
    content.video_playback_details = None

    started = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="article_detail"),
    )
    result = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(progress_percent=25, watched_seconds_delta=1),
    )
    persisted = repository.sessions[started.view_session_id]

    assert result.is_counted is True
    assert persisted.is_counted is True
    assert persisted.counted_at is not None
    assert persisted.counted_date is not None
    assert len(activity.content_views) == 1

    await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(progress_percent=50, watched_seconds_delta=5),
    )
    assert len(activity.content_views) == 1
    assert content.views_count == 1


@pytest.mark.anyio
async def test_article_view_session_counts_at_read_seconds_threshold(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    content.content_type = ContentTypeEnum.ARTICLE
    content.video_playback_details = None

    started = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="article_detail"),
    )
    result = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(progress_percent=5, watched_seconds_delta=10),
    )

    assert result.is_counted is True
    assert result.views_count == 1
    assert content.views_count == 1


@pytest.mark.anyio
async def test_article_view_session_below_threshold_does_not_count(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    content.content_type = ContentTypeEnum.ARTICLE
    content.video_playback_details = None

    started = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="article_detail"),
    )
    result = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(progress_percent=24, watched_seconds_delta=9),
    )

    assert result.is_counted is False
    assert result.views_count == 0
    assert content.views_count == 0


@pytest.mark.anyio
async def test_view_session_rejects_unpublished_content(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    content.content_type = ContentTypeEnum.POST
    content.status = ContentStatusEnum.DRAFT

    with pytest.raises(ContentNotFound):
        await service.start_view_session(
            content_id=content.content_id,
            user=viewer,
            data=ContentViewSessionStart(source="post_detail"),
        )


def test_view_session_heartbeat_position_is_optional_and_progress_validates() -> None:
    heartbeat = ContentViewSessionHeartbeat(progress_percent=25, watched_seconds_delta=1)

    assert heartbeat.position_seconds is None
    assert heartbeat.progress_percent == 25
    with pytest.raises(ValidationError):
        ContentViewSessionHeartbeat(progress_percent=101)


@pytest.mark.anyio
async def test_view_session_counts_once_per_viewer_content_day(service_bundle) -> None:
    service, repository, content, _author, viewer = service_bundle

    started = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="video_detail"),
    )
    counted = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(position_seconds=31, duration_seconds=100, watched_seconds_delta=31),
    )
    assert counted.views_count == 1
    second = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="video_detail"),
    )
    await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=second.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(position_seconds=40, duration_seconds=100, watched_seconds_delta=40),
    )

    assert counted.is_counted is True
    assert content.views_count == 1
    assert len(repository.sessions) == 2


@pytest.mark.anyio
async def test_author_view_session_increments_public_views_once(service_bundle) -> None:
    service, _repository, content, author, _viewer = service_bundle

    started = await service.start_view_session(
        content_id=content.content_id,
        user=author,
        data=ContentViewSessionStart(source="video_detail"),
    )
    result = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=author,
        data=ContentViewSessionHeartbeat(position_seconds=60, duration_seconds=100, watched_seconds_delta=60),
    )

    assert result.is_counted is True
    assert result.views_count == 1
    assert content.views_count == 1


@pytest.mark.anyio
async def test_moment_view_session_counts_after_two_seconds(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    content.content_type = ContentTypeEnum.MOMENT
    content.video_playback_details.duration_seconds = 90

    started = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="moments_feed"),
    )
    result = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(position_seconds=2, duration_seconds=90, watched_seconds_delta=2),
    )

    assert result.is_counted is True
    assert result.views_count == 1
    assert content.views_count == 1


@pytest.mark.anyio
async def test_moment_view_session_counts_at_half_progress_for_short_video(service_bundle) -> None:
    service, _repository, content, _author, viewer = service_bundle
    content.content_type = ContentTypeEnum.MOMENT
    content.video_playback_details.duration_seconds = 3

    started = await service.start_view_session(
        content_id=content.content_id,
        user=viewer,
        data=ContentViewSessionStart(source="moments_feed"),
    )
    result = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=viewer,
        data=ContentViewSessionHeartbeat(position_seconds=2, duration_seconds=3, watched_seconds_delta=1),
    )

    assert result.is_counted is True
    assert result.views_count == 1


@pytest.mark.anyio
async def test_moment_author_view_session_does_not_increment_public_views(service_bundle) -> None:
    service, _repository, content, author, _viewer = service_bundle
    content.content_type = ContentTypeEnum.MOMENT
    content.video_playback_details.duration_seconds = 30

    started = await service.start_view_session(
        content_id=content.content_id,
        user=author,
        data=ContentViewSessionStart(source="moments_feed"),
    )
    result = await service.heartbeat_view_session(
        content_id=content.content_id,
        session_id=started.view_session_id,
        user=author,
        data=ContentViewSessionHeartbeat(position_seconds=10, duration_seconds=30, watched_seconds_delta=10),
    )

    assert result.is_counted is True
    assert result.views_count == 0
    assert content.views_count == 0


@pytest.mark.anyio
async def test_publications_owner_and_non_owner_visibility_filters(service_bundle) -> None:
    service, repository, content, author, viewer = service_bundle
    now = datetime.datetime.now(datetime.timezone.utc)

    content.content_type = ContentTypeEnum.POST
    content.video_playback_details = None
    content.post_details = FakePostDetails(body_text="public")

    private_post = FakeContent(
        content_id=uuid.uuid4(),
        author_id=author.user_id,
        author=author,
        content_type=ContentTypeEnum.POST,
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=now,
        updated_at=now,
        published_at=now,
        video_playback_details=None,
        post_details=FakePostDetails(body_text="private"),
    )
    draft_post = FakeContent(
        content_id=uuid.uuid4(),
        author_id=author.user_id,
        author=author,
        content_type=ContentTypeEnum.POST,
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=now,
        updated_at=now,
        published_at=None,
        video_playback_details=None,
        post_details=FakePostDetails(body_text="draft"),
    )

    repository.publications = [content, private_post, draft_post]

    owner_items = await service.get_publications(
        author_id=author.user_id,
        viewer_id=author.user_id,
        content_type=None,
        profile_filter=ContentProfileFilterEnum.ALL,
        order=ContentOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=20,
    )
    viewer_items = await service.get_publications(
        author_id=author.user_id,
        viewer_id=viewer.user_id,
        content_type=None,
        profile_filter=ContentProfileFilterEnum.ALL,
        order=ContentOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=20,
    )
    owner_drafts = await service.get_publications(
        author_id=author.user_id,
        viewer_id=author.user_id,
        content_type=None,
        profile_filter=ContentProfileFilterEnum.DRAFTS,
        order=ContentOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=20,
    )

    assert len(owner_items) == 3
    assert len(viewer_items) == 1
    assert viewer_items[0].content_id == content.content_id
    assert len(owner_drafts) == 1
    assert owner_drafts[0].status == ContentStatusEnum.DRAFT


@pytest.mark.anyio
async def test_gallery_returns_post_media_items(monkeypatch, service_bundle) -> None:
    service, repository, content, author, viewer = service_bundle
    content.content_type = ContentTypeEnum.POST
    content.status = ContentStatusEnum.PUBLISHED
    content.visibility = ContentVisibilityEnum.PUBLIC
    content.video_playback_details = None
    content.post_details = FakePostDetails(body_text="gallery post")
    content.asset_links = [FakeLink(position=2)]
    repository.gallery_posts = [content]

    async def fake_build_attachment(link, *, storage):  # type: ignore[no-untyped-def]
        return PostAttachmentGet(
            asset_id=link.asset.asset_id,
            attachment_type=AttachmentTypeEnum.MEDIA,
            position=link.position,
            asset_type=AssetTypeEnum.IMAGE,
            mime_type="image/jpeg",
            file_kind="image",
            preview_url="https://cdn.test/preview.jpg",
            original_url="https://cdn.test/original.jpg",
        )

    monkeypatch.setattr("src.content.service.build_post_attachment_get", fake_build_attachment)

    items = await service.get_gallery(
        author_id=author.user_id,
        viewer_id=viewer.user_id,
        profile_filter=ContentProfileFilterEnum.PUBLIC,
        order=ContentOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=20,
    )

    assert len(items) == 1
    assert items[0].post_id == content.content_id
    assert items[0].position == 2
    assert items[0].attachment.preview_url == "https://cdn.test/preview.jpg"
