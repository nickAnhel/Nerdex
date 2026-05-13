import datetime
import uuid
from dataclasses import dataclass, field

import pytest

from src.articles.enums import ArticleOrder, ArticleProfileFilter
from src.articles.exceptions import ArticleNotFound, InvalidArticle
from src.articles.schemas import ArticleCreate, ArticleUpdate
from src.articles.service import ArticleService
from src.assets.enums import (
    AssetAccessTypeEnum,
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
    AttachmentTypeEnum,
)
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.tags.service import TagService
from src.users.schemas import UserGet


@dataclass
class FakeArticleDetails:
    slug: str
    body_markdown: str
    word_count: int
    reading_time_minutes: int
    toc: list[dict[str, str | int]]


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
    created_at: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


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
class FakeArticle:
    content_id: uuid.UUID
    author_id: uuid.UUID
    author: UserGet
    title: str
    excerpt: str
    article_details: FakeArticleDetails
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


class FakeArticleRepository:
    def __init__(self, users: dict[uuid.UUID, UserGet], assets: dict[uuid.UUID, FakeAsset]) -> None:
        self.users = users
        self.assets = assets
        self.articles: dict[uuid.UUID, FakeArticle] = {}
        self.reactions: dict[tuple[uuid.UUID, uuid.UUID], ReactionTypeEnum] = {}

    async def create(
        self,
        *,
        author_id: uuid.UUID,
        title: str,
        excerpt: str,
        body_markdown: str,
        slug: str,
        word_count: int,
        reading_time_minutes: int,
        toc: list[dict[str, str | int]],
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        created_at: datetime.datetime,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        commit: bool = True,
    ) -> FakeArticle:
        article = FakeArticle(
            content_id=uuid.uuid4(),
            author_id=author_id,
            author=self.users[author_id],
            title=title,
            excerpt=excerpt,
            article_details=FakeArticleDetails(
                slug=slug,
                body_markdown=body_markdown,
                word_count=word_count,
                reading_time_minutes=reading_time_minutes,
                toc=toc,
            ),
            status=status,
            visibility=visibility,
            created_at=created_at,
            updated_at=updated_at,
            published_at=published_at,
        )
        self.articles[article.content_id] = article
        return self._decorate(article, viewer_id=article.author_id)

    async def get_single(self, *, content_id: uuid.UUID, viewer_id: uuid.UUID | None = None):
        article = self.articles.get(content_id)
        if article is None:
            return None
        return self._decorate(article, viewer_id=viewer_id)

    async def get_feed(self, **kwargs):  # type: ignore[no-untyped-def]
        articles = [
            article for article in self.articles.values()
            if article.status == ContentStatusEnum.PUBLISHED
            and article.visibility == ContentVisibilityEnum.PUBLIC
            and article.deleted_at is None
        ]
        return [self._decorate(article, viewer_id=kwargs["viewer_id"]) for article in articles]

    async def get_author_articles(self, **kwargs):  # type: ignore[no-untyped-def]
        author_id = kwargs["author_id"]
        viewer_id = kwargs["viewer_id"]
        profile_filter = kwargs["profile_filter"]
        articles = [
            article for article in self.articles.values()
            if article.author_id == author_id and article.deleted_at is None
        ]
        if viewer_id == author_id:
            if profile_filter == ArticleProfileFilter.ALL:
                articles = [article for article in articles if article.status in {ContentStatusEnum.DRAFT, ContentStatusEnum.PUBLISHED}]
            elif profile_filter == ArticleProfileFilter.DRAFTS:
                articles = [article for article in articles if article.status == ContentStatusEnum.DRAFT]
            elif profile_filter == ArticleProfileFilter.PRIVATE:
                articles = [article for article in articles if article.status == ContentStatusEnum.PUBLISHED and article.visibility == ContentVisibilityEnum.PRIVATE]
            else:
                articles = [article for article in articles if article.status == ContentStatusEnum.PUBLISHED and article.visibility == ContentVisibilityEnum.PUBLIC]
        else:
            articles = [article for article in articles if article.status == ContentStatusEnum.PUBLISHED and article.visibility == ContentVisibilityEnum.PUBLIC]
        return [self._decorate(article, viewer_id=viewer_id) for article in articles]

    async def update_article(
        self,
        *,
        content_id: uuid.UUID,
        title: str,
        excerpt: str,
        body_markdown: str,
        slug: str,
        word_count: int,
        reading_time_minutes: int,
        toc: list[dict[str, str | int]],
        status: ContentStatusEnum,
        visibility: ContentVisibilityEnum,
        updated_at: datetime.datetime,
        published_at: datetime.datetime | None,
        commit: bool = True,
    ) -> FakeArticle:
        article = self.articles[content_id]
        article.title = title
        article.excerpt = excerpt
        article.status = status
        article.visibility = visibility
        article.updated_at = updated_at
        article.published_at = published_at
        article.article_details.slug = slug
        article.article_details.body_markdown = body_markdown
        article.article_details.word_count = word_count
        article.article_details.reading_time_minutes = reading_time_minutes
        article.article_details.toc = toc
        return self._decorate(article, viewer_id=article.author_id)

    async def commit(self) -> None:
        return None

    async def get_attachment_asset_ids(self, *, content_id: uuid.UUID) -> set[uuid.UUID]:
        article = self.articles[content_id]
        return {link.asset_id for link in article.asset_links if link.deleted_at is None}

    async def replace_asset_links(self, *, content_id: uuid.UUID, attachments: list[dict[str, object]], commit: bool = True) -> None:
        article = self.articles[content_id]
        article.asset_links = [
            FakeContentAsset(
                content_id=content_id,
                asset_id=attachment["asset_id"],  # type: ignore[index]
                attachment_type=attachment["attachment_type"],  # type: ignore[index]
                position=attachment["position"],  # type: ignore[index]
                asset=self.assets[attachment["asset_id"]],  # type: ignore[index]
            )
            for attachment in attachments
        ]

    async def soft_delete_article(self, **kwargs):  # type: ignore[no-untyped-def]
        article = self.articles[kwargs["content_id"]]
        article.status = ContentStatusEnum.DELETED
        article.deleted_at = kwargs["deleted_at"]
        article.updated_at = kwargs["updated_at"]
        return self._decorate(article, viewer_id=article.author_id)

    async def set_reaction(self, *, content_id: uuid.UUID, user_id: uuid.UUID, reaction_type: ReactionTypeEnum) -> None:
        article = self.articles[content_id]
        existing = self.reactions.get((content_id, user_id))
        if existing == reaction_type:
            return
        if existing == ReactionTypeEnum.LIKE:
            article.likes_count -= 1
        if existing == ReactionTypeEnum.DISLIKE:
            article.dislikes_count -= 1
        if reaction_type == ReactionTypeEnum.LIKE:
            article.likes_count += 1
        else:
            article.dislikes_count += 1
        self.reactions[(content_id, user_id)] = reaction_type

    async def remove_reaction(self, *, content_id: uuid.UUID, user_id: uuid.UUID, reaction_type: ReactionTypeEnum) -> None:
        article = self.articles[content_id]
        existing = self.reactions.get((content_id, user_id))
        if existing != reaction_type:
            return
        if reaction_type == ReactionTypeEnum.LIKE:
            article.likes_count -= 1
        else:
            article.dislikes_count -= 1
        del self.reactions[(content_id, user_id)]

    def _decorate(self, article: FakeArticle, viewer_id: uuid.UUID | None) -> FakeArticle:
        article.my_reaction = self.reactions.get((article.content_id, viewer_id)) if viewer_id is not None else None
        article.is_owner = viewer_id == article.author_id
        return article


class FakeTagRepository:
    def __init__(self) -> None:
        self.tags: dict[str, FakeTag] = {}
        self.content_tags: dict[uuid.UUID, list[uuid.UUID]] = {}

    async def resolve_tags(self, normalized_slugs: list[str]) -> list[FakeTag]:
        result = []
        for slug in normalized_slugs:
            if slug not in self.tags:
                self.tags[slug] = FakeTag(tag_id=uuid.uuid4(), slug=slug)
            result.append(self.tags[slug])
        return result

    async def replace_content_tags(self, *, content_id: uuid.UUID, tag_ids: list[uuid.UUID], commit: bool = True) -> None:
        self.content_tags[content_id] = list(tag_ids)


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


class FakeAssetService:
    def __init__(self) -> None:
        self.orphaned_asset_ids: list[uuid.UUID] = []

    async def mark_asset_orphaned_if_unreferenced(self, *, asset_id: uuid.UUID) -> bool:
        self.orphaned_asset_ids.append(asset_id)
        return True


class FakeStorage:
    async def generate_presigned_get(self, *, bucket: str, key: str, **kwargs) -> str:
        return f"https://cdn.example/{bucket}/{key}"


@dataclass
class ServiceBundle:
    service: ArticleService
    repository: FakeArticleRepository
    asset_service: FakeAssetService
    author: UserGet
    stranger: UserGet
    image_asset: FakeAsset
    inline_asset: FakeAsset
    video_asset: FakeAsset


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _make_asset(*, owner_id: uuid.UUID, asset_type: AssetTypeEnum, usage_context: str | None = None) -> FakeAsset:
    asset_id = uuid.uuid4()
    mime_type = "image/png" if asset_type == AssetTypeEnum.IMAGE else "video/mp4"
    extension = "png" if asset_type == AssetTypeEnum.IMAGE else "mp4"
    return FakeAsset(
        asset_id=asset_id,
        owner_id=owner_id,
        asset_type=asset_type,
        original_filename=f"asset.{extension}",
        status=AssetStatusEnum.READY,
        detected_mime_type=mime_type,
        size_bytes=1024,
        asset_metadata={"usage_context": usage_context} if usage_context else {},
        variants=[
            FakeVariant(
                asset_variant_type=AssetVariantTypeEnum.ORIGINAL,
                storage_bucket="private",
                storage_key=f"{asset_id}/original.{extension}",
                mime_type=mime_type,
                size_bytes=1024,
            )
        ],
    )


@pytest.fixture
def service_bundle() -> ServiceBundle:
    author_id = uuid.uuid4()
    stranger_id = uuid.uuid4()
    author = UserGet(
        user_id=author_id,
        username="author",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
        is_subscribed=False,
    )
    stranger = UserGet(
        user_id=stranger_id,
        username="stranger",
        is_admin=False,
        subscribers_count=0,
        avatar=None,
        avatar_asset_id=None,
        is_subscribed=False,
    )
    image_asset = _make_asset(owner_id=author_id, asset_type=AssetTypeEnum.IMAGE, usage_context="article_cover")
    inline_asset = _make_asset(owner_id=author_id, asset_type=AssetTypeEnum.IMAGE, usage_context="article_inline_image")
    video_asset = _make_asset(owner_id=author_id, asset_type=AssetTypeEnum.VIDEO, usage_context="article_video")
    assets = {
        image_asset.asset_id: image_asset,
        inline_asset.asset_id: inline_asset,
        video_asset.asset_id: video_asset,
    }
    repository = FakeArticleRepository(users={author_id: author, stranger_id: stranger}, assets=assets)
    asset_repository = FakeAssetRepository(assets)
    asset_service = FakeAssetService()
    tag_service = TagService(FakeTagRepository())
    service = ArticleService(
        repository=repository,
        tag_service=tag_service,
        asset_repository=asset_repository,
        asset_service=asset_service,  # type: ignore[arg-type]
        asset_storage=FakeStorage(),  # type: ignore[arg-type]
    )
    return ServiceBundle(
        service=service,
        repository=repository,
        asset_service=asset_service,
        author=author,
        stranger=stranger,
        image_asset=image_asset,
        inline_asset=inline_asset,
        video_asset=video_asset,
    )


@pytest.mark.anyio
async def test_create_article_creates_draft_with_cover_and_referenced_assets(service_bundle: ServiceBundle) -> None:
    article = await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Designing Articles",
            body_markdown=(
                "## Intro\n"
                f'::image{{asset-id="{service_bundle.inline_asset.asset_id}" size="wide" caption="Inline"}}\n'
                f'::video{{asset-id="{service_bundle.video_asset.asset_id}" size="wide" caption="Demo"}}\n'
            ),
            cover_asset_id=service_bundle.image_asset.asset_id,
            tags=["python", "backend"],
        ),
    )

    assert article.status == ContentStatusEnum.DRAFT
    assert article.visibility == ContentVisibilityEnum.PRIVATE
    assert article.slug == "designing-articles"
    assert article.cover is not None
    assert [asset.asset_id for asset in article.referenced_assets] == [
        service_bundle.inline_asset.asset_id,
        service_bundle.video_asset.asset_id,
    ]
    assert article.reading_time_minutes >= 1


@pytest.mark.anyio
async def test_published_article_slug_is_frozen(service_bundle: ServiceBundle) -> None:
    article = await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Ship It",
            body_markdown="## Intro\nText",
            status="published",
            visibility="public",
        ),
    )

    with pytest.raises(InvalidArticle, match="slug"):
        await service_bundle.service.update_article(
            user=service_bundle.author,
            article_id=article.article_id,
            data=ArticleUpdate(slug="changed-slug"),
        )


@pytest.mark.anyio
async def test_private_article_is_hidden_from_stranger(service_bundle: ServiceBundle) -> None:
    article = await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Private",
            body_markdown="## Intro\nBody",
        ),
    )

    with pytest.raises(ArticleNotFound):
        await service_bundle.service.get_article(article.article_id, user=service_bundle.stranger)


@pytest.mark.anyio
async def test_update_article_replaces_asset_set_and_marks_removed_assets_orphaned(service_bundle: ServiceBundle) -> None:
    article = await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Assets",
            body_markdown=f'::image{{asset-id="{service_bundle.inline_asset.asset_id}" size="wide"}}',
            cover_asset_id=service_bundle.image_asset.asset_id,
        ),
    )

    replacement_image = _make_asset(owner_id=service_bundle.author.user_id, asset_type=AssetTypeEnum.IMAGE, usage_context="article_inline_image")
    service_bundle.repository.assets[replacement_image.asset_id] = replacement_image
    service_bundle.service._asset_repository.assets[replacement_image.asset_id] = replacement_image  # type: ignore[attr-defined]

    updated = await service_bundle.service.update_article(
        user=service_bundle.author,
        article_id=article.article_id,
        data=ArticleUpdate(
            cover_asset_id=None,
            body_markdown=f'::image{{asset-id="{replacement_image.asset_id}" size="wide"}}',
        ),
    )

    assert updated.cover is None
    assert [asset.asset_id for asset in updated.referenced_assets] == [replacement_image.asset_id]
    assert set(service_bundle.asset_service.orphaned_asset_ids) == {
        service_bundle.image_asset.asset_id,
        service_bundle.inline_asset.asset_id,
    }


@pytest.mark.anyio
async def test_delete_article_marks_assets_orphaned(service_bundle: ServiceBundle) -> None:
    article = await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Delete me",
            body_markdown=f'::image{{asset-id="{service_bundle.inline_asset.asset_id}" size="wide"}}',
            cover_asset_id=service_bundle.image_asset.asset_id,
        ),
    )

    await service_bundle.service.delete_article(
        user=service_bundle.author,
        article_id=article.article_id,
    )

    assert set(service_bundle.asset_service.orphaned_asset_ids) == {
        service_bundle.image_asset.asset_id,
        service_bundle.inline_asset.asset_id,
    }


@pytest.mark.anyio
async def test_draft_article_does_not_accept_reaction(service_bundle: ServiceBundle) -> None:
    article = await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Draft reactions",
            body_markdown="## Intro\nBody",
        ),
    )

    with pytest.raises(ArticleNotFound):
        await service_bundle.service.add_like_to_article(
            article_id=article.article_id,
            user_id=service_bundle.stranger.user_id,
        )


@pytest.mark.anyio
async def test_get_articles_returns_only_public_items_for_stranger(service_bundle: ServiceBundle) -> None:
    await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Public item",
            body_markdown="## Intro\nBody",
            status="published",
            visibility="public",
        ),
    )
    await service_bundle.service.create_article(
        user=service_bundle.author,
        data=ArticleCreate(
            title="Private item",
            body_markdown="## Intro\nBody",
            status="published",
            visibility="private",
        ),
    )

    articles = await service_bundle.service.get_articles(
        order=ArticleOrder.PUBLISHED_AT,
        desc=True,
        offset=0,
        limit=10,
        user_id=service_bundle.author.user_id,
        user=service_bundle.stranger,
        profile_filter=ArticleProfileFilter.PUBLIC,
    )

    assert [article.title for article in articles] == ["Public item"]
