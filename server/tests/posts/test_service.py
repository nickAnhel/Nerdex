import datetime
import uuid
from dataclasses import dataclass, field

import pytest

from src.assets.enums import (
    AttachmentTypeEnum,
    AssetAccessTypeEnum,
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
)
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.posts.enums import PostOrder, PostProfileFilter
from src.posts.exceptions import InvalidPost, PostNotFound
from src.posts.schemas import PostAttachmentWrite, PostCreate, PostUpdate
from src.posts.service import PostService
from src.tags.service import TagService
from src.users.schemas import UserGet


@dataclass
class FakePostDetails:
    body_text: str


@dataclass
class FakeTag:
    tag_id: uuid.UUID
    slug: str


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
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


@dataclass
class FakeAsset:
    asset_id: uuid.UUID
    owner_id: uuid.UUID
    asset_type: AssetTypeEnum
    original_filename: str
    status: AssetStatusEnum
    access_type: AssetAccessTypeEnum = AssetAccessTypeEnum.PRIVATE
    detected_mime_type: str | None = None
    size_bytes: int | None = None
    asset_metadata: dict[str, object] = field(default_factory=dict)
    variants: list[FakeVariant] = field(default_factory=list)


@dataclass
class FakeContentAsset:
    content_id: uuid.UUID
    asset_id: uuid.UUID
    attachment_type: AttachmentTypeEnum
    position: int
    asset: FakeAsset
    deleted_at: datetime.datetime | None = None


@dataclass
class FakePost:
    content_id: uuid.UUID
    author_id: uuid.UUID
    author: UserGet
    post_details: FakePostDetails
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    deleted_at: datetime.datetime | None = None
    comments_count: int = 0
    likes_count: int = 0
    dislikes_count: int = 0
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool = False
    tags: list[FakeTag] = field(default_factory=list)
    asset_links: list[FakeContentAsset] = field(default_factory=list)

    @property
    def post_id(self) -> uuid.UUID:
        return self.content_id

    @property
    def user_id(self) -> uuid.UUID:
        return self.author_id

    @property
    def user(self) -> UserGet:
        return self.author

    @property
    def content(self) -> str:
        return self.post_details.body_text


class FakePostRepository:
    def __init__(self, users: dict[uuid.UUID, UserGet], assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.users = users
        self.assets = assets
        self.posts: dict[uuid.UUID, FakePost] = {}
        self.reactions: dict[tuple[uuid.UUID, uuid.UUID], ReactionTypeEnum] = {}
        self.subscriptions: set[tuple[uuid.UUID, uuid.UUID]] = set()

    async def create(
        self,
        *,
        author_id: uuid.UUID,
        body_text: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        created_at: datetime.datetime,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        commit: bool = True,
    ) -> FakePost:
        post = FakePost(
            content_id=uuid.uuid4(),
            author_id=author_id,
            author=self.users[author_id],
            post_details=FakePostDetails(body_text=body_text),
            status=status,
            visibility=visibility,
            created_at=created_at,
            updated_at=updated_at,
            published_at=published_at,
        )
        self.posts[post.content_id] = post
        return self._decorate(post, viewer_id=author_id)

    async def get_single(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None = None,
    ) -> FakePost | None:
        post = self.posts.get(content_id)
        if post is None:
            return None
        return self._decorate(post, viewer_id=viewer_id)

    async def get_feed(
        self,
        *,
        viewer_id: uuid.UUID | None,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        posts = [
            post for post in self.posts.values()
            if post.status == ContentStatusEnum.PUBLISHED
            and post.visibility == ContentVisibilityEnum.PUBLIC
            and post.deleted_at is None
        ]
        return self._decorate_many(
            posts=posts,
            viewer_id=viewer_id,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
        )

    async def get_author_posts(
        self,
        *,
        author_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        profile_filter: PostProfileFilter,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        posts = [
            post for post in self.posts.values()
            if post.author_id == author_id and post.deleted_at is None
        ]

        if viewer_id == author_id:
            if profile_filter == PostProfileFilter.ALL:
                posts = [
                    post for post in posts
                    if post.status in {ContentStatusEnum.PUBLISHED, ContentStatusEnum.DRAFT}
                ]
            elif profile_filter == PostProfileFilter.DRAFTS:
                posts = [post for post in posts if post.status == ContentStatusEnum.DRAFT]
            elif profile_filter == PostProfileFilter.PRIVATE:
                posts = [
                    post for post in posts
                    if post.status == ContentStatusEnum.PUBLISHED
                    and post.visibility == ContentVisibilityEnum.PRIVATE
                ]
            else:
                posts = [
                    post for post in posts
                    if post.status == ContentStatusEnum.PUBLISHED
                    and post.visibility == ContentVisibilityEnum.PUBLIC
                ]
        else:
            posts = [
                post for post in posts
                if post.status == ContentStatusEnum.PUBLISHED
                and post.visibility == ContentVisibilityEnum.PUBLIC
            ]

        return self._decorate_many(
            posts=posts,
            viewer_id=viewer_id,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
        )

    async def get_user_subscriptions_posts(
        self,
        *,
        user_id: uuid.UUID,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        subscribed_ids = {
            subscribed_id
            for subscriber_id, subscribed_id in self.subscriptions
            if subscriber_id == user_id
        }
        posts = [
            post for post in self.posts.values()
            if post.author_id in subscribed_ids
            and post.status == ContentStatusEnum.PUBLISHED
            and post.visibility == ContentVisibilityEnum.PUBLIC
            and post.deleted_at is None
        ]
        return self._decorate_many(
            posts=posts,
            viewer_id=user_id,
            order=order,
            order_desc=order_desc,
            offset=offset,
            limit=limit,
        )

    async def update_post(
        self,
        *,
        content_id: uuid.UUID,
        body_text: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        commit: bool = True,
    ) -> FakePost:
        post = self.posts[content_id]
        post.post_details.body_text = body_text
        post.status = status
        post.visibility = visibility
        post.updated_at = updated_at
        post.published_at = published_at
        return self._decorate(post, viewer_id=post.author_id)

    async def commit(self) -> None:
        return None

    async def get_attachment_asset_ids(
        self,
        *,
        content_id: uuid.UUID,
    ) -> set[uuid.UUID]:
        post = self.posts[content_id]
        return {link.asset_id for link in post.asset_links}

    async def replace_attachments(
        self,
        *,
        content_id: uuid.UUID,
        attachments: list[dict[str, object]],
        commit: bool = True,
    ) -> None:
        post = self.posts[content_id]
        post.asset_links = [
            FakeContentAsset(
                content_id=content_id,
                asset_id=attachment["asset_id"],  # type: ignore[index]
                attachment_type=attachment["attachment_type"],  # type: ignore[index]
                position=attachment["position"],  # type: ignore[index]
                asset=self.assets[attachment["asset_id"]],  # type: ignore[index]
            )
            for attachment in sorted(
                attachments,
                key=lambda item: (item["attachment_type"].value, item["position"]),  # type: ignore[index]
            )
        ]

    async def soft_delete_post(
        self,
        *,
        content_id: uuid.UUID,
        updated_at: datetime.datetime,
        deleted_at: datetime.datetime,
        commit: bool = True,
    ) -> FakePost:
        post = self.posts[content_id]
        post.status = ContentStatusEnum.DELETED
        post.updated_at = updated_at
        post.deleted_at = deleted_at
        return self._decorate(post, viewer_id=post.author_id)

    async def set_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        post = self.posts[content_id]
        current = self.reactions.get((content_id, user_id))
        if current == reaction_type:
            return

        if current is None:
            if reaction_type == ReactionTypeEnum.LIKE:
                post.likes_count += 1
            else:
                post.dislikes_count += 1
        elif current == ReactionTypeEnum.LIKE:
            post.likes_count -= 1
            post.dislikes_count += 1
        else:
            post.dislikes_count -= 1
            post.likes_count += 1

        self.reactions[(content_id, user_id)] = reaction_type

    async def remove_reaction(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        current = self.reactions.get((content_id, user_id))
        if current != reaction_type:
            return

        post = self.posts[content_id]
        if reaction_type == ReactionTypeEnum.LIKE:
            post.likes_count -= 1
        else:
            post.dislikes_count -= 1

        del self.reactions[(content_id, user_id)]

    def seed_post(
        self,
        *,
        author: UserGet,
        content: str,
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        created_at: datetime.datetime,
        published_at: datetime.datetime | None = None,
        deleted_at: datetime.datetime | None = None,
    ) -> FakePost:
        post = FakePost(
            content_id=uuid.uuid4(),
            author_id=author.user_id,
            author=author,
            post_details=FakePostDetails(body_text=content),
            status=status,
            visibility=visibility,
            created_at=created_at,
            updated_at=created_at,
            published_at=published_at,
            deleted_at=deleted_at,
        )
        self.posts[post.content_id] = post
        return post

    def _decorate_many(
        self,
        *,
        posts: list[FakePost],
        viewer_id: uuid.UUID | None,
        order: PostOrder,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[FakePost]:
        order_attr = {
            PostOrder.ID: "content_id",
            PostOrder.CREATED_AT: "created_at",
            PostOrder.UPDATED_AT: "updated_at",
            PostOrder.PUBLISHED_AT: "published_at",
        }[order]
        ordered_posts = sorted(
            posts,
            key=lambda post: (getattr(post, order_attr) is None, getattr(post, order_attr)),
            reverse=order_desc,
        )
        return [
            self._decorate(post, viewer_id=viewer_id)
            for post in ordered_posts[offset: offset + limit]
        ]

    def _decorate(self, post: FakePost, viewer_id: uuid.UUID | None) -> FakePost:
        post.is_owner = viewer_id == post.author_id
        post.my_reaction = self.reactions.get((post.content_id, viewer_id)) if viewer_id else None
        return post


class FakeAssetRepository:
    def __init__(self, assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.assets = assets

    async def get_assets(
        self,
        *,
        asset_ids: list[uuid.UUID],
        owner_id: uuid.UUID | None = None,
    ) -> list[FakeAsset]:
        resolved_assets: list[FakeAsset] = []
        for asset_id in asset_ids:
            asset = self.assets.get(asset_id)
            if asset is None:
                continue
            if owner_id is not None and asset.owner_id != owner_id:
                continue
            resolved_assets.append(asset)
        return resolved_assets


class FakeAssetService:
    def __init__(self) -> None:
        self.orphaned_asset_ids: list[uuid.UUID] = []

    async def mark_asset_orphaned_if_unreferenced(self, *, asset_id: uuid.UUID) -> bool:
        self.orphaned_asset_ids.append(asset_id)
        return True


class FakeAssetStorage:
    async def generate_presigned_get(
        self,
        *,
        bucket: str,
        key: str,
        download_filename: str | None = None,
        inline: bool = True,
        response_content_type: str | None = None,
    ) -> str:
        suffix = ""
        if download_filename:
            suffix = f"?download={download_filename}&inline={str(inline).lower()}"
        return f"https://download.test/{bucket}/{key}{suffix}"


class FakeTagRepository:
    def __init__(self, post_repository: FakePostRepository) -> None:
        self.post_repository = post_repository
        self.tags_by_slug: dict[str, FakeTag] = {}
        self.tags_by_id: dict[uuid.UUID, FakeTag] = {}
        self.content_tags: dict[uuid.UUID, list[uuid.UUID]] = {}

    async def suggest_tags(
        self,
        *,
        prefix: str,
        limit: int,
    ) -> list[FakeTag]:
        matching_tags = [
            tag for slug, tag in sorted(self.tags_by_slug.items())
            if slug.startswith(prefix)
        ]
        return matching_tags[:limit]

    async def resolve_tags(self, slugs: list[str]) -> list[FakeTag]:
        resolved_tags: list[FakeTag] = []
        for slug in slugs:
            existing_tag = self.tags_by_slug.get(slug)
            if existing_tag is None:
                existing_tag = FakeTag(tag_id=uuid.uuid4(), slug=slug)
                self.tags_by_slug[slug] = existing_tag
                self.tags_by_id[existing_tag.tag_id] = existing_tag
            resolved_tags.append(existing_tag)

        return resolved_tags

    async def replace_content_tags(
        self,
        *,
        content_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        commit: bool = True,
    ) -> None:
        unique_tag_ids = list(dict.fromkeys(tag_ids))
        unique_tag_ids.sort(key=lambda tag_id: self.tags_by_id[tag_id].slug)
        self.content_tags[content_id] = unique_tag_ids
        if content_id in self.post_repository.posts:
            self.post_repository.posts[content_id].tags = [
                self.tags_by_id[tag_id] for tag_id in unique_tag_ids
            ]

    def seed_tag(
        self,
        slug: str,
        *,
        content_id: uuid.UUID | None = None,
    ) -> FakeTag:
        tag = self.tags_by_slug.get(slug)
        if tag is None:
            tag = FakeTag(tag_id=uuid.uuid4(), slug=slug)
            self.tags_by_slug[slug] = tag
            self.tags_by_id[tag.tag_id] = tag

        if content_id is not None:
            content_tag_ids = self.content_tags.setdefault(content_id, [])
            if tag.tag_id not in content_tag_ids:
                content_tag_ids.append(tag.tag_id)
            content_tag_ids.sort(key=lambda tag_id: self.tags_by_id[tag_id].slug)
            if content_id in self.post_repository.posts:
                self.post_repository.posts[content_id].tags = [
                    self.tags_by_id[tag_id] for tag_id in content_tag_ids
                ]

        return tag


@dataclass
class ServiceBundle:
    service: PostService
    repository: FakePostRepository
    tag_repository: FakeTagRepository
    asset_repository: FakeAssetRepository
    asset_service: FakeAssetService
    author: UserGet
    stranger: UserGet
    follower: UserGet


def build_asset(
    *,
    owner_id: uuid.UUID,
    asset_type: AssetTypeEnum,
    filename: str,
    mime_type: str,
    usage_context: str | None,
    duration_ms: int | None = None,
) -> FakeAsset:
    asset_id = uuid.uuid4()
    variants = [
        FakeVariant(
            asset_variant_type=AssetVariantTypeEnum.ORIGINAL,
            storage_bucket="bucket",
            storage_key=f"{asset_id}/original",
            mime_type=mime_type,
            size_bytes=2048,
            width=1600 if asset_type == AssetTypeEnum.IMAGE else None,
            height=900 if asset_type == AssetTypeEnum.IMAGE else None,
            duration_ms=duration_ms,
        )
    ]
    if asset_type == AssetTypeEnum.IMAGE:
        variants.append(
            FakeVariant(
                asset_variant_type=AssetVariantTypeEnum.IMAGE_SMALL,
                storage_bucket="bucket",
                storage_key=f"{asset_id}/image_small.webp",
                mime_type="image/webp",
                size_bytes=512,
                width=640,
                height=640,
            )
        )
    return FakeAsset(
        asset_id=asset_id,
        owner_id=owner_id,
        asset_type=asset_type,
        original_filename=filename,
        status=AssetStatusEnum.READY,
        detected_mime_type=mime_type,
        size_bytes=2048,
        asset_metadata={"usage_context": usage_context} if usage_context else {},
        variants=variants,
    )


@pytest.fixture
def service_bundle() -> ServiceBundle:
    author = UserGet(
        user_id=uuid.uuid4(),
        username="author",
        is_admin=False,
        subscribers_count=0,
    )
    stranger = UserGet(
        user_id=uuid.uuid4(),
        username="stranger",
        is_admin=False,
        subscribers_count=0,
    )
    follower = UserGet(
        user_id=uuid.uuid4(),
        username="follower",
        is_admin=False,
        subscribers_count=0,
    )
    image_media = build_asset(
        owner_id=author.user_id,
        asset_type=AssetTypeEnum.IMAGE,
        filename="photo.png",
        mime_type="image/png",
        usage_context="post_media",
    )
    video_media = build_asset(
        owner_id=author.user_id,
        asset_type=AssetTypeEnum.VIDEO,
        filename="clip.mp4",
        mime_type="video/mp4",
        usage_context="post_media",
        duration_ms=42000,
    )
    file_asset = build_asset(
        owner_id=author.user_id,
        asset_type=AssetTypeEnum.FILE,
        filename="report.pdf",
        mime_type="application/pdf",
        usage_context="post_file",
    )
    audio_asset = build_asset(
        owner_id=author.user_id,
        asset_type=AssetTypeEnum.FILE,
        filename="voice.mp3",
        mime_type="audio/mpeg",
        usage_context="post_file",
        duration_ms=9000,
    )
    image_file_asset = build_asset(
        owner_id=author.user_id,
        asset_type=AssetTypeEnum.IMAGE,
        filename="scan.jpg",
        mime_type="image/jpeg",
        usage_context="post_file",
    )
    stranger_asset = build_asset(
        owner_id=stranger.user_id,
        asset_type=AssetTypeEnum.FILE,
        filename="secret.pdf",
        mime_type="application/pdf",
        usage_context="post_file",
    )
    avatar_asset = build_asset(
        owner_id=author.user_id,
        asset_type=AssetTypeEnum.IMAGE,
        filename="avatar.png",
        mime_type="image/png",
        usage_context="avatar",
    )
    assets = {
        asset.asset_id: asset
        for asset in [
            image_media,
            video_media,
            file_asset,
            audio_asset,
            image_file_asset,
            stranger_asset,
            avatar_asset,
        ]
    }

    repository = FakePostRepository(
        users={
            author.user_id: author,
            stranger.user_id: stranger,
            follower.user_id: follower,
        },
        assets=assets,
    )
    tag_repository = FakeTagRepository(post_repository=repository)
    asset_repository = FakeAssetRepository(assets)
    asset_service = FakeAssetService()
    repository.subscriptions.add((follower.user_id, author.user_id))
    return ServiceBundle(
        service=PostService(
            repository=repository,
            tag_service=TagService(repository=tag_repository),
            asset_repository=asset_repository,  # type: ignore[arg-type]
            asset_service=asset_service,  # type: ignore[arg-type]
            asset_storage=FakeAssetStorage(),  # type: ignore[arg-type]
        ),
        repository=repository,
        tag_repository=tag_repository,
        asset_repository=asset_repository,
        asset_service=asset_service,
        author=author,
        stranger=stranger,
        follower=follower,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def dt(minutes: int) -> datetime.datetime:
    return datetime.datetime(2026, 3, 9, 12, 0, tzinfo=datetime.timezone.utc) + datetime.timedelta(minutes=minutes)


def attachment_payload(
    asset_id: uuid.UUID,
    attachment_type: AttachmentTypeEnum,
    position: int,
) -> PostAttachmentWrite:
    return PostAttachmentWrite(
        asset_id=asset_id,
        attachment_type=attachment_type,
        position=position,
    )


def find_asset_id(service_bundle: ServiceBundle, filename: str) -> uuid.UUID:
    for asset_id, asset in service_bundle.asset_repository.assets.items():
        if asset.original_filename == filename:
            return asset_id
    raise AssertionError(f"Asset with filename {filename} not found")


@pytest.mark.anyio
async def test_create_post_creates_content_and_post_details(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="public body"),
    )

    stored = service_bundle.repository.posts[post.post_id]
    assert post.user_id == service_bundle.author.user_id
    assert post.content == "public body"
    assert post.status == ContentStatusEnum.PUBLISHED
    assert post.visibility == ContentVisibilityEnum.PUBLIC
    assert stored.post_details.body_text == "public body"
    assert post.tags == []


@pytest.mark.anyio
async def test_create_post_with_media_only(service_bundle: ServiceBundle) -> None:
    image_asset_id = find_asset_id(service_bundle, "photo.png")
    video_asset_id = find_asset_id(service_bundle, "clip.mp4")

    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            attachments=[
                attachment_payload(image_asset_id, AttachmentTypeEnum.MEDIA, 0),
                attachment_payload(video_asset_id, AttachmentTypeEnum.MEDIA, 1),
            ],
        ),
    )

    assert post.content == ""
    assert [attachment.asset_id for attachment in post.media_attachments] == [image_asset_id, video_asset_id]
    assert post.file_attachments == []


@pytest.mark.anyio
async def test_create_post_with_files_only(service_bundle: ServiceBundle) -> None:
    file_asset_id = find_asset_id(service_bundle, "report.pdf")
    audio_asset_id = find_asset_id(service_bundle, "voice.mp3")

    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            attachments=[
                attachment_payload(file_asset_id, AttachmentTypeEnum.FILE, 0),
                attachment_payload(audio_asset_id, AttachmentTypeEnum.FILE, 1),
            ],
        ),
    )

    assert post.content == ""
    assert [attachment.asset_id for attachment in post.file_attachments] == [file_asset_id, audio_asset_id]
    assert post.media_attachments == []
    assert post.file_attachments[1].is_audio is True


@pytest.mark.anyio
async def test_create_post_with_text_media_files_and_tags(service_bundle: ServiceBundle) -> None:
    image_asset_id = find_asset_id(service_bundle, "photo.png")
    file_asset_id = find_asset_id(service_bundle, "report.pdf")

    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            content="full post",
            tags=["python", "backend"],
            attachments=[
                attachment_payload(image_asset_id, AttachmentTypeEnum.MEDIA, 0),
                attachment_payload(file_asset_id, AttachmentTypeEnum.FILE, 0),
            ],
        ),
    )

    assert post.content == "full post"
    assert [tag.slug for tag in post.tags] == ["backend", "python"]
    assert [attachment.asset_id for attachment in post.media_attachments] == [image_asset_id]
    assert [attachment.asset_id for attachment in post.file_attachments] == [file_asset_id]


@pytest.mark.anyio
async def test_create_post_rejects_tags_only_payload(service_bundle: ServiceBundle) -> None:
    with pytest.raises(InvalidPost):
        await service_bundle.service.create_post(
            service_bundle.author,
            PostCreate(content="", tags=["python"]),
        )


@pytest.mark.anyio
async def test_create_post_rejects_more_than_thirty_media_attachments(service_bundle: ServiceBundle) -> None:
    asset_ids: list[uuid.UUID] = []
    for index in range(31):
        asset = build_asset(
            owner_id=service_bundle.author.user_id,
            asset_type=AssetTypeEnum.IMAGE,
            filename=f"extra-{index}.png",
            mime_type="image/png",
            usage_context="post_media",
        )
        service_bundle.asset_repository.assets[asset.asset_id] = asset
        service_bundle.repository.assets[asset.asset_id] = asset
        asset_ids.append(asset.asset_id)

    with pytest.raises(InvalidPost):
        await service_bundle.service.create_post(
            service_bundle.author,
            PostCreate(
                attachments=[
                    attachment_payload(asset_ids[position], AttachmentTypeEnum.MEDIA, position)
                    for position in range(len(asset_ids))
                ],
            ),
        )


@pytest.mark.anyio
async def test_create_post_rejects_more_than_ten_file_attachments(service_bundle: ServiceBundle) -> None:
    asset_ids: list[uuid.UUID] = []
    for index in range(11):
        asset = build_asset(
            owner_id=service_bundle.author.user_id,
            asset_type=AssetTypeEnum.FILE,
            filename=f"extra-{index}.pdf",
            mime_type="application/pdf",
            usage_context="post_file",
        )
        service_bundle.asset_repository.assets[asset.asset_id] = asset
        service_bundle.repository.assets[asset.asset_id] = asset
        asset_ids.append(asset.asset_id)

    with pytest.raises(InvalidPost):
        await service_bundle.service.create_post(
            service_bundle.author,
            PostCreate(
                attachments=[
                    attachment_payload(asset_ids[position], AttachmentTypeEnum.FILE, position)
                    for position in range(len(asset_ids))
                ],
            ),
        )


@pytest.mark.anyio
async def test_create_post_with_new_tags_creates_tags_and_links(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="tagged body", tags=["python", "тест"]),
    )

    stored = service_bundle.repository.posts[post.post_id]
    assert [tag.slug for tag in post.tags] == ["python", "тест"]
    assert [tag.slug for tag in stored.tags] == ["python", "тест"]
    assert set(service_bundle.tag_repository.tags_by_slug) == {"python", "тест"}


@pytest.mark.anyio
async def test_create_post_reuses_existing_tags_without_duplicates(service_bundle: ServiceBundle) -> None:
    existing = service_bundle.tag_repository.seed_tag("python")

    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="reuse tag", tags=["python"]),
    )

    assert len(service_bundle.tag_repository.tags_by_slug) == 1
    assert post.tags[0].tag_id == existing.tag_id


@pytest.mark.anyio
async def test_create_post_collapses_duplicate_tags(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="dedupe tags", tags=["python", "python", "тест", "python"]),
    )

    assert [tag.slug for tag in post.tags] == ["python", "тест"]


@pytest.mark.anyio
async def test_create_private_post_creates_published_private_post(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="private body", visibility="private"),
    )

    assert post.status == ContentStatusEnum.PUBLISHED
    assert post.visibility == ContentVisibilityEnum.PRIVATE
    assert post.published_at is not None


@pytest.mark.anyio
async def test_create_draft_post_creates_draft_post(service_bundle: ServiceBundle) -> None:
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(content="draft body", status="draft"),
    )

    assert post.status == ContentStatusEnum.DRAFT
    assert post.published_at is None


@pytest.mark.anyio
async def test_get_post_returns_public_published_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public post",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(0),
        published_at=dt(0),
    )
    service_bundle.tag_repository.seed_tag("python", content_id=post.content_id)
    service_bundle.tag_repository.seed_tag("backend", content_id=post.content_id)

    result = await service_bundle.service.get_post(post.content_id, user=service_bundle.stranger)

    assert result.post_id == post.content_id
    assert result.content == "public post"
    assert [tag.slug for tag in result.tags] == ["backend", "python"]


@pytest.mark.anyio
async def test_get_post_returns_private_post_to_author(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private post",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(1),
        published_at=dt(1),
    )

    result = await service_bundle.service.get_post(post.content_id, user=service_bundle.author)

    assert result.post_id == post.content_id
    assert result.is_owner is True


@pytest.mark.anyio
async def test_get_post_does_not_return_private_post_to_stranger(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private post",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(2),
        published_at=dt(2),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.get_post(post.content_id, user=service_bundle.stranger)


@pytest.mark.anyio
async def test_get_post_returns_draft_post_to_author(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft post",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(3),
    )

    result = await service_bundle.service.get_post(post.content_id, user=service_bundle.author)

    assert result.post_id == post.content_id
    assert result.status == ContentStatusEnum.DRAFT


@pytest.mark.anyio
async def test_get_post_does_not_return_draft_post_to_stranger(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft post",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(4),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.get_post(post.content_id, user=service_bundle.stranger)


@pytest.mark.anyio
async def test_update_post_updates_body_text_and_updated_at(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="before",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(5),
        published_at=dt(5),
    )
    old_updated_at = post.updated_at

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.content_id,
        PostUpdate(content="after"),
    )

    assert updated.content == "after"
    assert updated.updated_at > old_updated_at


@pytest.mark.anyio
async def test_update_post_can_reorder_media_attachments(service_bundle: ServiceBundle) -> None:
    image_asset_id = find_asset_id(service_bundle, "photo.png")
    video_asset_id = find_asset_id(service_bundle, "clip.mp4")
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            attachments=[
                attachment_payload(image_asset_id, AttachmentTypeEnum.MEDIA, 0),
                attachment_payload(video_asset_id, AttachmentTypeEnum.MEDIA, 1),
            ],
        ),
    )

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.post_id,
        PostUpdate(
            attachments=[
                attachment_payload(video_asset_id, AttachmentTypeEnum.MEDIA, 0),
                attachment_payload(image_asset_id, AttachmentTypeEnum.MEDIA, 1),
            ],
        ),
    )

    assert [attachment.asset_id for attachment in updated.media_attachments] == [video_asset_id, image_asset_id]


@pytest.mark.anyio
async def test_update_post_can_reorder_file_attachments(service_bundle: ServiceBundle) -> None:
    file_asset_id = find_asset_id(service_bundle, "report.pdf")
    audio_asset_id = find_asset_id(service_bundle, "voice.mp3")
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            attachments=[
                attachment_payload(file_asset_id, AttachmentTypeEnum.FILE, 0),
                attachment_payload(audio_asset_id, AttachmentTypeEnum.FILE, 1),
            ],
        ),
    )

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.post_id,
        PostUpdate(
            attachments=[
                attachment_payload(audio_asset_id, AttachmentTypeEnum.FILE, 0),
                attachment_payload(file_asset_id, AttachmentTypeEnum.FILE, 1),
            ],
        ),
    )

    assert [attachment.asset_id for attachment in updated.file_attachments] == [audio_asset_id, file_asset_id]


@pytest.mark.anyio
async def test_image_added_via_file_block_remains_file_attachment(service_bundle: ServiceBundle) -> None:
    image_file_asset_id = find_asset_id(service_bundle, "scan.jpg")

    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            attachments=[
                attachment_payload(image_file_asset_id, AttachmentTypeEnum.FILE, 0),
            ],
        ),
    )

    assert post.media_attachments == []
    assert len(post.file_attachments) == 1
    assert post.file_attachments[0].attachment_type == AttachmentTypeEnum.FILE
    assert post.file_attachments[0].asset_type == AssetTypeEnum.IMAGE


@pytest.mark.anyio
async def test_get_post_returns_structured_attachment_response_with_download_links(service_bundle: ServiceBundle) -> None:
    image_asset_id = find_asset_id(service_bundle, "photo.png")
    file_asset_id = find_asset_id(service_bundle, "report.pdf")
    audio_asset_id = find_asset_id(service_bundle, "voice.mp3")
    created = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            content="attachments",
            attachments=[
                attachment_payload(image_asset_id, AttachmentTypeEnum.MEDIA, 0),
                attachment_payload(file_asset_id, AttachmentTypeEnum.FILE, 0),
                attachment_payload(audio_asset_id, AttachmentTypeEnum.FILE, 1),
            ],
        ),
    )

    post = await service_bundle.service.get_post(created.post_id, user=service_bundle.author)

    assert len(post.media_attachments) == 1
    assert len(post.file_attachments) == 2
    assert post.media_attachments[0].preview_url is not None
    assert post.media_attachments[0].original_url is not None
    assert post.file_attachments[0].download_url is not None
    assert "download=report.pdf" in post.file_attachments[0].download_url
    assert post.file_attachments[1].stream_url is not None
    assert post.file_attachments[1].is_audio is True


@pytest.mark.anyio
async def test_create_post_rejects_attachment_from_another_owner(service_bundle: ServiceBundle) -> None:
    stranger_asset_id = find_asset_id(service_bundle, "secret.pdf")

    with pytest.raises(InvalidPost):
        await service_bundle.service.create_post(
            service_bundle.author,
            PostCreate(
                attachments=[
                    attachment_payload(stranger_asset_id, AttachmentTypeEnum.FILE, 0),
                ],
            ),
        )


@pytest.mark.anyio
async def test_create_post_rejects_avatar_usage_context(service_bundle: ServiceBundle) -> None:
    avatar_asset_id = find_asset_id(service_bundle, "avatar.png")

    with pytest.raises(InvalidPost):
        await service_bundle.service.create_post(
            service_bundle.author,
            PostCreate(
                attachments=[
                    attachment_payload(avatar_asset_id, AttachmentTypeEnum.MEDIA, 0),
                ],
            ),
        )


@pytest.mark.anyio
async def test_update_post_replaces_attachment_set_and_marks_removed_assets_orphaned(service_bundle: ServiceBundle) -> None:
    image_asset_id = find_asset_id(service_bundle, "photo.png")
    video_asset_id = find_asset_id(service_bundle, "clip.mp4")
    file_asset_id = find_asset_id(service_bundle, "report.pdf")
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            content="before",
            attachments=[
                attachment_payload(image_asset_id, AttachmentTypeEnum.MEDIA, 0),
                attachment_payload(file_asset_id, AttachmentTypeEnum.FILE, 0),
            ],
        ),
    )

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.post_id,
        PostUpdate(
            content="after",
            attachments=[
                attachment_payload(video_asset_id, AttachmentTypeEnum.MEDIA, 0),
            ],
        ),
    )

    assert updated.content == "after"
    assert [attachment.asset_id for attachment in updated.media_attachments] == [video_asset_id]
    assert updated.file_attachments == []
    assert set(service_bundle.asset_service.orphaned_asset_ids) == {image_asset_id, file_asset_id}


@pytest.mark.anyio
async def test_update_post_replaces_tags_set(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="before",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(5),
        published_at=dt(5),
    )
    service_bundle.tag_repository.seed_tag("old", content_id=post.content_id)

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.content_id,
        PostUpdate(tags=["new", "ещё"]),
    )

    assert [tag.slug for tag in updated.tags] == ["new", "ещё"]
    assert [tag.slug for tag in service_bundle.repository.posts[post.content_id].tags] == ["new", "ещё"]


@pytest.mark.anyio
async def test_update_post_can_remove_all_tags(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="before",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(5),
        published_at=dt(5),
    )
    service_bundle.tag_repository.seed_tag("old", content_id=post.content_id)

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.content_id,
        PostUpdate(tags=[]),
    )

    assert updated.tags == []
    assert service_bundle.repository.posts[post.content_id].tags == []


@pytest.mark.anyio
async def test_update_post_without_tags_does_not_change_existing_tags(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="before",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(5),
        published_at=dt(5),
    )
    service_bundle.tag_repository.seed_tag("keep", content_id=post.content_id)

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.content_id,
        PostUpdate(content="after"),
    )

    assert updated.content == "after"
    assert [tag.slug for tag in updated.tags] == ["keep"]


@pytest.mark.anyio
async def test_update_post_on_deleted_post_is_forbidden(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(6),
        deleted_at=dt(7),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.update_post(
            service_bundle.author,
            post.content_id,
            PostUpdate(content="after"),
        )


@pytest.mark.anyio
async def test_publish_draft_sets_published_at(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(8),
    )

    updated = await service_bundle.service.update_post(
        service_bundle.author,
        post.content_id,
        PostUpdate(status="published"),
    )

    assert updated.status == ContentStatusEnum.PUBLISHED
    assert updated.published_at is not None


@pytest.mark.anyio
async def test_delete_post_soft_deletes_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="delete me",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(9),
        published_at=dt(9),
    )

    await service_bundle.service.delete_post(service_bundle.author, post.content_id)

    stored = service_bundle.repository.posts[post.content_id]
    assert stored.status == ContentStatusEnum.DELETED
    assert stored.deleted_at is not None


@pytest.mark.anyio
async def test_delete_post_marks_removed_attachments_orphaned(service_bundle: ServiceBundle) -> None:
    image_asset_id = find_asset_id(service_bundle, "photo.png")
    file_asset_id = find_asset_id(service_bundle, "report.pdf")
    post = await service_bundle.service.create_post(
        service_bundle.author,
        PostCreate(
            content="delete me",
            attachments=[
                attachment_payload(image_asset_id, AttachmentTypeEnum.MEDIA, 0),
                attachment_payload(file_asset_id, AttachmentTypeEnum.FILE, 0),
            ],
        ),
    )

    await service_bundle.service.delete_post(service_bundle.author, post.post_id)

    assert set(service_bundle.asset_service.orphaned_asset_ids) >= {image_asset_id, file_asset_id}
    assert service_bundle.repository.posts[post.post_id].asset_links == []


@pytest.mark.anyio
async def test_delete_post_repeated_is_predictable(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="delete me",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(10),
        published_at=dt(10),
    )

    await service_bundle.service.delete_post(service_bundle.author, post.content_id)
    deleted_at = service_bundle.repository.posts[post.content_id].deleted_at
    await service_bundle.service.delete_post(service_bundle.author, post.content_id)

    assert service_bundle.repository.posts[post.content_id].deleted_at == deleted_at


@pytest.mark.anyio
async def test_like_from_neutral(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(11),
        published_at=dt(11),
    )

    rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0
    assert rating.my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.anyio
async def test_dislike_from_neutral(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(12),
        published_at=dt(12),
    )

    rating = await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1
    assert rating.my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_switch_dislike_to_like(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(13),
        published_at=dt(13),
    )
    await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0
    assert rating.my_reaction == ReactionTypeEnum.LIKE


@pytest.mark.anyio
async def test_switch_like_to_dislike(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(14),
        published_at=dt(14),
    )
    await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1
    assert rating.my_reaction == ReactionTypeEnum.DISLIKE


@pytest.mark.anyio
async def test_remove_like(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(15),
        published_at=dt(15),
    )
    await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.remove_like_from_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.my_reaction is None


@pytest.mark.anyio
async def test_remove_dislike(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(16),
        published_at=dt(16),
    )
    await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.remove_dislike_from_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.dislikes_count == 0
    assert rating.my_reaction is None


@pytest.mark.anyio
async def test_repeat_like_is_idempotent(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(17),
        published_at=dt(17),
    )
    await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 1
    assert rating.dislikes_count == 0


@pytest.mark.anyio
async def test_repeat_dislike_is_idempotent(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="react",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(18),
        published_at=dt(18),
    )
    await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    rating = await service_bundle.service.add_dislike_to_post(post.content_id, service_bundle.stranger.user_id)

    assert rating.likes_count == 0
    assert rating.dislikes_count == 1


@pytest.mark.anyio
async def test_cannot_react_to_draft_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(19),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.add_like_to_post(post.content_id, service_bundle.author.user_id)


@pytest.mark.anyio
async def test_cannot_react_to_deleted_post(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(20),
        deleted_at=dt(21),
    )

    with pytest.raises(PostNotFound):
        await service_bundle.service.add_like_to_post(post.content_id, service_bundle.author.user_id)


@pytest.mark.anyio
async def test_private_published_post_accepts_reaction_only_from_visible_user(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(22),
        published_at=dt(22),
    )

    owner_rating = await service_bundle.service.add_like_to_post(post.content_id, service_bundle.author.user_id)

    assert owner_rating.my_reaction == ReactionTypeEnum.LIKE

    with pytest.raises(PostNotFound):
        await service_bundle.service.add_like_to_post(post.content_id, service_bundle.stranger.user_id)


@pytest.mark.anyio
async def test_post_list_returns_my_reaction_correctly(service_bundle: ServiceBundle) -> None:
    first = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="first",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(23),
        published_at=dt(23),
    )
    second = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="second",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(24),
        published_at=dt(24),
    )
    service_bundle.repository.reactions[(first.content_id, service_bundle.stranger.user_id)] = ReactionTypeEnum.LIKE
    first.likes_count = 1

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )

    by_id = {post.post_id: post for post in posts}
    assert by_id[first.content_id].my_reaction == ReactionTypeEnum.LIKE
    assert by_id[second.content_id].my_reaction is None


@pytest.mark.anyio
async def test_subscriptions_list_returns_my_reaction_correctly(service_bundle: ServiceBundle) -> None:
    post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="subscription",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(25),
        published_at=dt(25),
    )
    service_bundle.repository.reactions[(post.content_id, service_bundle.follower.user_id)] = ReactionTypeEnum.DISLIKE
    post.dislikes_count = 1
    service_bundle.tag_repository.seed_tag("python", content_id=post.content_id)

    posts = await service_bundle.service.get_user_subscriptions_posts(
        user_id=service_bundle.follower.user_id,
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
    )

    assert len(posts) == 1
    assert posts[0].my_reaction == ReactionTypeEnum.DISLIKE
    assert [tag.slug for tag in posts[0].tags] == ["python"]


@pytest.mark.anyio
async def test_feed_does_not_include_private_posts(service_bundle: ServiceBundle) -> None:
    public_post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(26),
        published_at=dt(26),
    )
    private_post = service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(27),
        published_at=dt(27),
    )
    service_bundle.tag_repository.seed_tag("feed", content_id=public_post.content_id)
    service_bundle.tag_repository.seed_tag("hidden", content_id=private_post.content_id)

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )

    assert [post.content for post in posts] == ["public"]
    assert [tag.slug for tag in posts[0].tags] == ["feed"]


@pytest.mark.anyio
async def test_feed_does_not_include_drafts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(28),
        published_at=dt(28),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(29),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )

    assert [post.content for post in posts] == ["public"]


@pytest.mark.anyio
async def test_author_profile_public_filter_returns_only_public_published(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(30),
        published_at=dt(30),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(31),
        published_at=dt(31),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(32),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.PUBLIC,
    )

    assert [post.content for post in posts] == ["public"]


@pytest.mark.anyio
async def test_author_profile_all_filter_returns_all_non_deleted_posts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(32),
        published_at=dt(32),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(33),
        published_at=dt(33),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(34),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(35),
        deleted_at=dt(36),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.ALL,
    )

    assert [post.content for post in posts] == ["draft", "private", "public"]


@pytest.mark.anyio
async def test_author_profile_private_filter_returns_only_private_published(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(33),
        published_at=dt(33),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(34),
        published_at=dt(34),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.PRIVATE,
    )

    assert [post.content for post in posts] == ["private"]


@pytest.mark.anyio
async def test_author_profile_drafts_filter_returns_only_drafts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(35),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(36),
        published_at=dt(36),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.DRAFTS,
    )

    assert [post.content for post in posts] == ["draft"]


@pytest.mark.anyio
async def test_other_profile_does_not_show_private_or_drafts(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="public",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(37),
        published_at=dt(37),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="private",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PRIVATE,
        created_at=dt(38),
        published_at=dt(38),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="draft",
        status=ContentStatusEnum.DRAFT,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(39),
    )

    posts = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.stranger,
        profile_filter=PostProfileFilter.DRAFTS,
    )

    assert [post.content for post in posts] == ["public"]


@pytest.mark.anyio
async def test_deleted_posts_do_not_appear_in_regular_lists(service_bundle: ServiceBundle) -> None:
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="visible",
        status=ContentStatusEnum.PUBLISHED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(40),
        published_at=dt(40),
    )
    service_bundle.repository.seed_post(
        author=service_bundle.author,
        content="deleted",
        status=ContentStatusEnum.DELETED,
        visibility=ContentVisibilityEnum.PUBLIC,
        created_at=dt(41),
        deleted_at=dt(42),
    )

    feed = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user=service_bundle.stranger,
    )
    profile = await service_bundle.service.get_posts(
        order=PostOrder.CREATED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.author,
        profile_filter=PostProfileFilter.PUBLIC,
    )

    assert [post.content for post in feed] == ["visible"]
    assert [post.content for post in profile] == ["visible"]
