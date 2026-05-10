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
from src.content.enums import ContentStatusEnum, ContentTypeEnum, ContentVisibilityEnum
from src.moments.exceptions import InvalidMoment, MomentNotFound
from src.moments.schemas import MomentCreate
from src.moments.service import MomentService
from src.tags.service import TagService
from src.users.schemas import UserGet
from src.videos.enums import VideoOrientationEnum, VideoProcessingStatusEnum


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
class FakeMomentDetails:
    caption: str
    publish_requested_at: datetime.datetime | None = None


@dataclass
class FakePlayback:
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
class FakeMoment:
    content_id: uuid.UUID
    author_id: uuid.UUID
    author: UserGet
    content_type: ContentTypeEnum
    moment_details: FakeMomentDetails
    video_playback_details: FakePlayback
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    excerpt: str = ""
    comments_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    views_count: int = 0
    my_reaction: object | None = None
    is_owner: bool = False
    tags: list = field(default_factory=list)
    asset_links: list[FakeContentAsset] = field(default_factory=list)


class FakeMomentRepository:
    def __init__(self, users: dict[uuid.UUID, UserGet], assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.users = users
        self.assets = assets
        self.moments: dict[uuid.UUID, FakeMoment] = {}

    async def create(self, **kwargs):  # type: ignore[no-untyped-def]
        moment = FakeMoment(
            content_id=uuid.uuid4(),
            author_id=kwargs["author_id"],
            author=self.users[kwargs["author_id"]],
            content_type=ContentTypeEnum.MOMENT,
            moment_details=FakeMomentDetails(
                caption=kwargs["caption"],
                publish_requested_at=kwargs["publish_requested_at"],
            ),
            video_playback_details=FakePlayback(
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
            excerpt=kwargs["excerpt"],
            created_at=kwargs["created_at"],
            updated_at=kwargs["updated_at"],
            published_at=kwargs["published_at"],
        )
        self.moments[moment.content_id] = moment
        return self._decorate(moment, viewer_id=moment.author_id)

    async def get_single(self, *, content_id: uuid.UUID, viewer_id: uuid.UUID | None = None):
        moment = self.moments.get(content_id)
        return self._decorate(moment, viewer_id=viewer_id) if moment is not None else None

    async def get_feed(self, *, viewer_id: uuid.UUID | None, offset: int, limit: int):
        items = [
            moment
            for moment in self.moments.values()
            if moment.status == ContentStatusEnum.PUBLISHED
            and moment.visibility == ContentVisibilityEnum.PUBLIC
            and moment.deleted_at is None
            and moment.video_playback_details.processing_status == VideoProcessingStatusEnum.READY
        ]
        return [self._decorate(moment, viewer_id=viewer_id) for moment in items[offset:offset + limit]]

    async def replace_asset_links(self, *, content_id: uuid.UUID, attachments: list[dict[str, object]], commit: bool = True) -> None:
        self.moments[content_id].asset_links = [
            FakeContentAsset(
                content_id=content_id,
                asset_id=attachment["asset_id"],  # type: ignore[index]
                attachment_type=attachment["attachment_type"],  # type: ignore[index]
                position=attachment["position"],  # type: ignore[index]
                asset=self.assets[attachment["asset_id"]],  # type: ignore[index]
            )
            for attachment in attachments
        ]

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
        for moment in self.moments.values():
            if not any(link.asset_id == asset_id and link.attachment_type == AttachmentTypeEnum.VIDEO_SOURCE for link in moment.asset_links):
                continue
            moment.video_playback_details.duration_seconds = duration_seconds
            moment.video_playback_details.width = width
            moment.video_playback_details.height = height
            moment.video_playback_details.orientation = orientation
            moment.video_playback_details.processing_status = processing_status
            moment.video_playback_details.available_quality_metadata = available_quality_metadata
            moment.video_playback_details.processing_error = processing_error
            if processing_status == VideoProcessingStatusEnum.READY and moment.moment_details.publish_requested_at:
                if orientation == VideoOrientationEnum.PORTRAIT and duration_seconds is not None and duration_seconds <= 90:
                    moment.status = ContentStatusEnum.PUBLISHED
                    moment.published_at = moment.published_at or now
                    moment.video_playback_details.processing_error = None
                else:
                    moment.video_playback_details.processing_error = "Publish validation failed: moment source must be portrait"

    async def get_attachment_asset_ids(self, *, content_id: uuid.UUID) -> set[uuid.UUID]:
        return {link.asset_id for link in self.moments[content_id].asset_links}

    async def commit(self) -> None:
        return None

    def _decorate(self, moment: FakeMoment, viewer_id: uuid.UUID | None) -> FakeMoment:
        moment.is_owner = moment.author_id == viewer_id
        return moment


class FakeAssetRepository:
    def __init__(self, assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.assets = assets

    async def get_assets(self, *, asset_ids: list[uuid.UUID], owner_id: uuid.UUID | None = None) -> list[FakeAsset]:
        return [
            asset
            for asset_id in asset_ids
            if (asset := self.assets.get(asset_id)) is not None
            and (owner_id is None or asset.owner_id == owner_id)
        ]


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
    service: MomentService
    repository: FakeMomentRepository
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


def _make_asset(
    owner_id: uuid.UUID,
    asset_type: AssetTypeEnum,
    *,
    status: AssetStatusEnum = AssetStatusEnum.READY,
    width: int = 720,
    height: int = 1280,
    duration_seconds: int = 30,
) -> FakeAsset:
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
            width=width if is_video else 720,
            height=height if is_video else 1280,
            duration_ms=duration_seconds * 1000 if is_video else None,
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
                width=width,
                height=height,
                duration_ms=duration_seconds * 1000,
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
            "duration_seconds": duration_seconds,
            "width": width,
            "height": height,
            "orientation": "portrait" if height > width else "landscape",
        } if is_video and status == AssetStatusEnum.READY else {},
        variants=variants,
    )


@pytest.fixture
def bundle() -> Bundle:
    author = _make_user("author")
    stranger = _make_user("stranger")
    source_asset = _make_asset(author.user_id, AssetTypeEnum.VIDEO, status=AssetStatusEnum.PROCESSING)
    cover_asset = _make_asset(author.user_id, AssetTypeEnum.IMAGE)
    assets = {source_asset.asset_id: source_asset, cover_asset.asset_id: cover_asset}
    repository = FakeMomentRepository(users={author.user_id: author, stranger.user_id: stranger}, assets=assets)
    service = MomentService(
        repository=repository,  # type: ignore[arg-type]
        tag_service=TagService(repository=FakeTagRepository()),  # type: ignore[arg-type]
        asset_repository=FakeAssetRepository(assets),  # type: ignore[arg-type]
        asset_service=FakeAssetService(),  # type: ignore[arg-type]
        asset_storage=FakeStorage(),  # type: ignore[arg-type]
    )
    return Bundle(service=service, repository=repository, author=author, stranger=stranger, source_asset=source_asset, cover_asset=cover_asset)


@pytest.mark.anyio
async def test_publish_request_while_processing_keeps_moment_owner_only_draft(bundle: Bundle) -> None:
    moment = await bundle.service.create_moment(
        user=bundle.author,
        data=MomentCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            caption="Processing moment",
            visibility="public",
            status="published",
        ),
    )

    assert moment.status == ContentStatusEnum.DRAFT
    assert moment.publish_requested_at is not None
    assert moment.playback_sources == []
    with pytest.raises(MomentNotFound):
        await bundle.service.get_moment(moment_id=moment.moment_id, user=bundle.stranger)


@pytest.mark.anyio
async def test_create_moment_rejects_ready_landscape_video(bundle: Bundle) -> None:
    landscape = _make_asset(bundle.author.user_id, AssetTypeEnum.VIDEO, width=1280, height=720)
    bundle.repository.assets[landscape.asset_id] = landscape
    bundle.service._asset_repository.assets[landscape.asset_id] = landscape  # type: ignore[attr-defined]

    with pytest.raises(InvalidMoment):
        await bundle.service.create_moment(
            user=bundle.author,
            data=MomentCreate(source_asset_id=landscape.asset_id, cover_asset_id=bundle.cover_asset.asset_id),
        )


@pytest.mark.anyio
async def test_create_moment_rejects_ready_video_longer_than_90_seconds(bundle: Bundle) -> None:
    long_source = _make_asset(bundle.author.user_id, AssetTypeEnum.VIDEO, duration_seconds=91)
    bundle.repository.assets[long_source.asset_id] = long_source
    bundle.service._asset_repository.assets[long_source.asset_id] = long_source  # type: ignore[attr-defined]

    with pytest.raises(InvalidMoment):
        await bundle.service.create_moment(
            user=bundle.author,
            data=MomentCreate(source_asset_id=long_source.asset_id, cover_asset_id=bundle.cover_asset.asset_id),
        )


@pytest.mark.anyio
async def test_create_moment_rejects_foreign_or_wrong_type_assets(bundle: Bundle) -> None:
    foreign_cover = _make_asset(bundle.stranger.user_id, AssetTypeEnum.IMAGE)
    image_source = _make_asset(bundle.author.user_id, AssetTypeEnum.IMAGE)
    bundle.repository.assets[foreign_cover.asset_id] = foreign_cover
    bundle.repository.assets[image_source.asset_id] = image_source
    bundle.service._asset_repository.assets[foreign_cover.asset_id] = foreign_cover  # type: ignore[attr-defined]
    bundle.service._asset_repository.assets[image_source.asset_id] = image_source  # type: ignore[attr-defined]

    with pytest.raises(InvalidMoment):
        await bundle.service.create_moment(
            user=bundle.author,
            data=MomentCreate(source_asset_id=bundle.source_asset.asset_id, cover_asset_id=foreign_cover.asset_id),
        )
    with pytest.raises(InvalidMoment):
        await bundle.service.create_moment(
            user=bundle.author,
            data=MomentCreate(source_asset_id=image_source.asset_id, cover_asset_id=bundle.cover_asset.asset_id),
        )


@pytest.mark.anyio
async def test_processing_notifier_auto_publishes_valid_requested_moment_and_feed_includes_sources(bundle: Bundle) -> None:
    moment = await bundle.service.create_moment(
        user=bundle.author,
        data=MomentCreate(
            source_asset_id=bundle.source_asset.asset_id,
            cover_asset_id=bundle.cover_asset.asset_id,
            caption="Ready soon",
            visibility="public",
            status="published",
        ),
    )

    await bundle.repository.update_processing_for_source_asset(
        asset_id=bundle.source_asset.asset_id,
        processing_status=VideoProcessingStatusEnum.READY,
        duration_seconds=30,
        width=720,
        height=1280,
        orientation=VideoOrientationEnum.PORTRAIT,
        available_quality_metadata={"qualities": ["720p"]},
        processing_error=None,
        now=datetime.datetime.now(datetime.timezone.utc),
    )

    stored = bundle.repository.moments[moment.moment_id]
    assert stored.status == ContentStatusEnum.PUBLISHED
    feed = await bundle.service.get_feed(user=bundle.stranger, offset=0, limit=10)
    assert [item.moment_id for item in feed] == [moment.moment_id]
    assert [source.id for source in feed[0].playback_sources] == ["original"]
