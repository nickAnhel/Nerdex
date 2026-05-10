import datetime
import uuid
from dataclasses import dataclass, field

import pytest

from src.assets.enums import (
    AssetAccessTypeEnum,
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
    AttachmentTypeEnum,
)
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum
from src.tags.service import TagService
from src.users.schemas import UserGet
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum, VideoWriteStatus
from src.videos.exceptions import InvalidVideo
from src.videos.schemas import VideoCreate
from src.videos.service import VideoAssetProcessingNotifier, VideoProcessingAssetUpdate, VideoService


@dataclass
class FakeVariant:
    asset_variant_type: AssetVariantTypeEnum
    storage_bucket: str
    storage_key: str
    mime_type: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    duration_ms: int | None = None
    bitrate: int | None = None
    status: AssetVariantStatusEnum = AssetVariantStatusEnum.READY
    checksum_sha256: str | None = None
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


@dataclass
class FakeAsset:
    asset_id: uuid.UUID
    owner_id: uuid.UUID
    asset_type: AssetTypeEnum
    original_filename: str
    original_extension: str
    declared_mime_type: str
    detected_mime_type: str | None
    size_bytes: int
    status: AssetStatusEnum
    access_type: AssetAccessTypeEnum = AssetAccessTypeEnum.PRIVATE
    asset_metadata: dict[str, object] = field(default_factory=dict)
    variants: list[FakeVariant] = field(default_factory=list)


@dataclass
class FakeVideoDetails:
    description: str
    chapters: list[dict[str, object]]
    publish_requested_at: datetime.datetime | None = None


@dataclass
class FakeVideoPlaybackDetails:
    duration_seconds: int | None
    width: int | None
    height: int | None
    orientation: VideoOrientationEnum | None
    processing_status: VideoProcessingStatusEnum
    processing_error: str | None
    available_quality_metadata: dict[str, object]


@dataclass
class FakeContentAsset:
    content_id: uuid.UUID
    asset_id: uuid.UUID
    attachment_type: AttachmentTypeEnum
    position: int
    asset: FakeAsset
    deleted_at: datetime.datetime | None = None


@dataclass
class FakeVideo:
    content_id: uuid.UUID
    author_id: uuid.UUID
    author: UserGet
    content_type: object
    title: str
    excerpt: str
    video_details: FakeVideoDetails
    video_playback_details: FakeVideoPlaybackDetails
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    comments_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    my_reaction: object | None = None
    is_owner: bool = False
    tags: list = field(default_factory=list)
    asset_links: list[FakeContentAsset] = field(default_factory=list)


class FakeVideoRepository:
    def __init__(self, users: dict[uuid.UUID, UserGet], assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.users = users
        self.assets = assets
        self.videos: dict[uuid.UUID, FakeVideo] = {}

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        from src.content.enums import ContentTypeEnum

        video = FakeVideo(
            content_id=uuid.uuid4(),
            author_id=kwargs["author_id"],
            author=self.users[kwargs["author_id"]],
            content_type=ContentTypeEnum.VIDEO,
            title=kwargs["title"],
            excerpt=kwargs["excerpt"],
            video_details=FakeVideoDetails(
                description=kwargs["description"],
                chapters=kwargs["chapters"],
                publish_requested_at=kwargs["publish_requested_at"],
            ),
            video_playback_details=FakeVideoPlaybackDetails(
                duration_seconds=kwargs["duration_seconds"],
                width=kwargs["width"],
                height=kwargs["height"],
                orientation=kwargs["orientation"],
                processing_status=kwargs["processing_status"],
                processing_error=kwargs["processing_error"],
                available_quality_metadata=kwargs["available_quality_metadata"],
            ),
            status=kwargs["status"],
            visibility=kwargs["visibility"],
            created_at=kwargs["created_at"],
            updated_at=kwargs["updated_at"],
            published_at=kwargs["published_at"],
        )
        self.videos[video.content_id] = video
        return self._decorate(video, viewer_id=video.author_id)

    async def get_single(self, *, content_id: uuid.UUID, viewer_id: uuid.UUID | None = None):
        video = self.videos.get(content_id)
        return self._decorate(video, viewer_id=viewer_id) if video is not None else None

    async def replace_asset_links(self, *, content_id: uuid.UUID, attachments: list[dict[str, object]], commit: bool = True) -> None:
        self.videos[content_id].asset_links = [
            FakeContentAsset(
                content_id=content_id,
                asset_id=attachment["asset_id"],  # type: ignore[index]
                attachment_type=attachment["attachment_type"],  # type: ignore[index]
                position=attachment["position"],  # type: ignore[index]
                asset=self.assets[attachment["asset_id"]],  # type: ignore[index]
            )
            for attachment in attachments
        ]

    async def commit(self) -> None:
        return None

    async def update_processing_for_source_asset(
        self,
        *,
        asset_id: uuid.UUID,
        processing_status: VideoProcessingStatusEnum,
        duration_seconds: int | None,
        width: int | None,
        height: int | None,
        orientation: VideoOrientationEnum | None,
        available_quality_metadata: dict[str, object],
        processing_error: str | None,
        now: datetime.datetime,
    ) -> None:
        for video in self.videos.values():
            if not any(
                link.asset_id == asset_id
                and link.attachment_type == AttachmentTypeEnum.VIDEO_SOURCE
                and link.deleted_at is None
                for link in video.asset_links
            ):
                continue
            video.video_playback_details.duration_seconds = duration_seconds
            video.video_playback_details.width = width
            video.video_playback_details.height = height
            video.video_playback_details.orientation = orientation
            video.video_playback_details.processing_status = processing_status
            video.video_playback_details.processing_error = processing_error
            video.video_playback_details.available_quality_metadata = available_quality_metadata
            if processing_status == VideoProcessingStatusEnum.READY:
                await self._auto_publish_if_requested(video=video, now=now)

    async def _auto_publish_if_requested(self, *, video: FakeVideo, now: datetime.datetime) -> None:
        if video.video_details.publish_requested_at is None:
            return
        if video.status == ContentStatusEnum.PUBLISHED or video.deleted_at is not None:
            return
        if not (video.title or "").strip():
            video.video_playback_details.processing_error = "Publish validation failed: title is required"
            return
        has_cover = any(
            link.attachment_type == AttachmentTypeEnum.COVER and link.deleted_at is None
            for link in video.asset_links
        )
        if not has_cover:
            video.video_playback_details.processing_error = "Publish validation failed: cover asset is required"
            return
        video.status = ContentStatusEnum.PUBLISHED
        video.published_at = video.published_at or now
        video.updated_at = now
        video.video_playback_details.processing_error = None

    def _decorate(self, video: FakeVideo, viewer_id: uuid.UUID | None) -> FakeVideo:
        video.is_owner = video.author_id == viewer_id
        return video


class FakeAssetRepository:
    def __init__(self, assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.assets = assets

    async def get_assets(self, *, asset_ids: list[uuid.UUID], owner_id: uuid.UUID | None = None) -> list[FakeAsset]:
        result = []
        for asset_id in asset_ids:
            asset = self.assets.get(asset_id)
            if asset is None:
                continue
            if owner_id is not None and asset.owner_id != owner_id:
                continue
            result.append(asset)
        return result


class FakeTagRepository:
    async def resolve_tags(self, normalized_slugs: list[str]) -> list:
        return []

    async def replace_content_tags(self, *, content_id: uuid.UUID, tag_ids: list[uuid.UUID], commit: bool = True) -> None:
        return None


class FakeAssetService:
    async def mark_asset_orphaned_if_unreferenced(self, *, asset_id: uuid.UUID) -> bool:
        return True


class FakeStorage:
    async def generate_presigned_get(self, *, bucket: str, key: str, **kwargs) -> str:
        return f"https://cdn.example/{bucket}/{key}"


@dataclass
class Bundle:
    service: VideoService
    repository: FakeVideoRepository
    author: UserGet
    stranger: UserGet
    source_asset: FakeAsset
    cover_asset: FakeAsset


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _make_user(username: str) -> UserGet:
    return UserGet(
        user_id=uuid.uuid4(),
        username=username,
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
        is_subscribed=False,
    )


def _make_asset(owner_id: uuid.UUID, asset_type: AssetTypeEnum, *, status: AssetStatusEnum = AssetStatusEnum.READY) -> FakeAsset:
    asset_id = uuid.uuid4()
    is_video = asset_type == AssetTypeEnum.VIDEO
    mime_type = "video/mp4" if is_video else "image/webp"
    extension = "mp4" if is_video else "webp"
    variants = [
        FakeVariant(
            asset_variant_type=AssetVariantTypeEnum.ORIGINAL,
            storage_bucket="private",
            storage_key=f"{asset_id}/original.{extension}",
            mime_type=mime_type,
            size_bytes=1024,
            width=1920 if is_video else 1280,
            height=1080 if is_video else 720,
            duration_ms=60_000 if is_video else None,
        )
    ]
    if is_video and status == AssetStatusEnum.READY:
        variants.append(
            FakeVariant(
                asset_variant_type=AssetVariantTypeEnum.VIDEO_720P,
                storage_bucket="private",
                storage_key=f"{asset_id}/video_720p.mp4",
                mime_type="video/mp4",
                size_bytes=2048,
                width=1280,
                height=720,
                duration_ms=60_000,
            )
        )
    return FakeAsset(
        asset_id=asset_id,
        owner_id=owner_id,
        asset_type=asset_type,
        original_filename=f"asset.{extension}",
        original_extension=extension,
        declared_mime_type=mime_type,
        detected_mime_type=mime_type,
        size_bytes=1024,
        status=status,
        asset_metadata={
            "video_processing_status": "ready",
            "duration_seconds": 60,
            "width": 1920,
            "height": 1080,
            "orientation": "landscape",
        } if is_video and status == AssetStatusEnum.READY else {},
        variants=variants,
    )


@pytest.fixture
def bundle() -> Bundle:
    author = _make_user("author")
    stranger = _make_user("stranger")
    source_asset = _make_asset(author.user_id, AssetTypeEnum.VIDEO, status=AssetStatusEnum.PROCESSING)
    cover_asset = _make_asset(author.user_id, AssetTypeEnum.IMAGE)
    assets = {
        source_asset.asset_id: source_asset,
        cover_asset.asset_id: cover_asset,
    }
    repository = FakeVideoRepository(users={author.user_id: author, stranger.user_id: stranger}, assets=assets)
    service = VideoService(
        repository=repository,  # type: ignore[arg-type]
        tag_service=TagService(repository=FakeTagRepository()),  # type: ignore[arg-type]
        asset_repository=FakeAssetRepository(assets),  # type: ignore[arg-type]
        asset_service=FakeAssetService(),  # type: ignore[arg-type]
        asset_storage=FakeStorage(),  # type: ignore[arg-type]
    )
    return Bundle(service=service, repository=repository, author=author, stranger=stranger, source_asset=source_asset, cover_asset=cover_asset)


@pytest.mark.anyio
async def test_create_video_draft_requires_source_and_cover_assets(bundle: Bundle) -> None:
    video = await bundle.service.create_video(
        user=bundle.author,
        data=VideoCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            status=VideoWriteStatus.DRAFT,
        ),
    )

    assert video.status == ContentStatusEnum.DRAFT
    assert video.processing_status == VideoProcessingStatusEnum.TRANSCODING
    stored_video = bundle.repository.videos[video.video_id]
    assert {link.attachment_type for link in stored_video.asset_links} == {
        AttachmentTypeEnum.VIDEO_SOURCE,
        AttachmentTypeEnum.COVER,
    }


@pytest.mark.anyio
async def test_publish_request_while_processing_keeps_video_owner_only_draft(bundle: Bundle) -> None:
    video = await bundle.service.create_video(
        user=bundle.author,
        data=VideoCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            title="Processing video",
            visibility="public",
            status="published",
        ),
    )

    assert video.status == ContentStatusEnum.DRAFT
    assert video.publish_requested_at is not None
    with pytest.raises(Exception):
        await bundle.service.get_video(video_id=video.video_id, user=bundle.stranger)


@pytest.mark.anyio
async def test_video_processing_notifier_auto_publishes_requested_ready_video(bundle: Bundle) -> None:
    video = await bundle.service.create_video(
        user=bundle.author,
        data=VideoCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            title="Processing video",
            visibility="public",
            status="published",
        ),
    )

    await VideoAssetProcessingNotifier(bundle.repository).notify(
        VideoProcessingAssetUpdate(
            asset_id=bundle.source_asset.asset_id,
            processing_status=VideoProcessingStatusEnum.READY,
            duration_seconds=55,
            width=1920,
            height=1080,
            orientation=VideoOrientationEnum.LANDSCAPE,
            available_quality_metadata={"qualities": ["720p"]},
        )
    )

    stored_video = bundle.repository.videos[video.video_id]
    assert stored_video.status == ContentStatusEnum.PUBLISHED
    assert stored_video.published_at is not None
    assert stored_video.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
    assert stored_video.video_playback_details.processing_error is None


@pytest.mark.anyio
async def test_video_processing_notifier_keeps_requested_video_draft_when_publish_validation_fails(bundle: Bundle) -> None:
    video = await bundle.service.create_video(
        user=bundle.author,
        data=VideoCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            visibility="public",
            status="published",
        ),
    )

    await VideoAssetProcessingNotifier(bundle.repository).notify(
        VideoProcessingAssetUpdate(
            asset_id=bundle.source_asset.asset_id,
            processing_status=VideoProcessingStatusEnum.READY,
            duration_seconds=55,
            width=1920,
            height=1080,
            orientation=VideoOrientationEnum.LANDSCAPE,
            available_quality_metadata={"qualities": ["720p"]},
        )
    )

    stored_video = bundle.repository.videos[video.video_id]
    assert stored_video.status == ContentStatusEnum.DRAFT
    assert stored_video.video_playback_details.processing_error == "Publish validation failed: title is required"


@pytest.mark.anyio
async def test_ready_publish_without_title_stays_draft_with_error(bundle: Bundle) -> None:
    bundle.source_asset.status = AssetStatusEnum.READY
    bundle.source_asset.asset_metadata["video_processing_status"] = "ready"
    bundle.source_asset.variants.append(
        FakeVariant(
            asset_variant_type=AssetVariantTypeEnum.VIDEO_720P,
            storage_bucket="private",
            storage_key=f"{bundle.source_asset.asset_id}/video_720p.mp4",
            mime_type="video/mp4",
            size_bytes=2048,
            width=1280,
            height=720,
            duration_ms=60_000,
        )
    )

    video = await bundle.service.create_video(
        user=bundle.author,
        data=VideoCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            visibility="public",
            status="published",
        ),
    )

    assert video.status == ContentStatusEnum.DRAFT
    assert video.processing_error == "Publish validation failed: title is required"


@pytest.mark.anyio
async def test_ready_publish_returns_playback_sources(bundle: Bundle) -> None:
    bundle.source_asset.status = AssetStatusEnum.READY
    bundle.source_asset.asset_metadata["video_processing_status"] = "ready"
    bundle.source_asset.variants.append(
        FakeVariant(
            asset_variant_type=AssetVariantTypeEnum.VIDEO_720P,
            storage_bucket="private",
            storage_key=f"{bundle.source_asset.asset_id}/video_720p.mp4",
            mime_type="video/mp4",
            size_bytes=2048,
            width=1280,
            height=720,
            duration_ms=60_000,
        )
    )

    video = await bundle.service.create_video(
        user=bundle.author,
        data=VideoCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            title="Ready video",
            visibility="public",
            status="published",
        ),
    )

    assert video.status == ContentStatusEnum.PUBLISHED
    assert [source.id for source in video.playback_sources] == ["720p", "original"]


@pytest.mark.anyio
async def test_publish_accepts_processing_cover_with_ready_original(bundle: Bundle) -> None:
    bundle.source_asset.status = AssetStatusEnum.READY
    bundle.source_asset.asset_metadata["video_processing_status"] = "ready"
    bundle.source_asset.variants.append(
        FakeVariant(
            asset_variant_type=AssetVariantTypeEnum.VIDEO_720P,
            storage_bucket="private",
            storage_key=f"{bundle.source_asset.asset_id}/video_720p.mp4",
            mime_type="video/mp4",
            size_bytes=2048,
            width=1280,
            height=720,
            duration_ms=60_000,
        )
    )
    bundle.cover_asset.status = AssetStatusEnum.PROCESSING

    video = await bundle.service.create_video(
        user=bundle.author,
        data=VideoCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            title="Cover still processing",
            visibility="public",
            status="published",
        ),
    )

    assert video.status == ContentStatusEnum.PUBLISHED
    assert video.cover is not None
    assert video.cover.status == AssetStatusEnum.PROCESSING


@pytest.mark.anyio
async def test_create_video_rejects_foreign_cover_asset(bundle: Bundle) -> None:
    foreign_cover = _make_asset(bundle.stranger.user_id, AssetTypeEnum.IMAGE)
    bundle.repository.assets[foreign_cover.asset_id] = foreign_cover
    bundle.service._asset_repository.assets[foreign_cover.asset_id] = foreign_cover  # type: ignore[attr-defined]

    with pytest.raises(InvalidVideo):
        await bundle.service.create_video(
            user=bundle.author,
            data=VideoCreate(
                source_asset_id=bundle.source_asset.asset_id,
                cover_asset_id=foreign_cover.asset_id,
            ),
        )
