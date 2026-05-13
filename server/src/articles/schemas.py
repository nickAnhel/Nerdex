import datetime
import uuid

from pydantic import Field

from src.articles.enums import ArticleWriteStatus, ArticleWriteVisibility
from src.common.schemas import BaseSchema
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.tags.schemas import TagGet
from src.users.schemas import UserGet


class ArticleAssetGet(BaseSchema):
    asset_id: uuid.UUID
    attachment_type: str
    asset_type: str
    mime_type: str | None = None
    file_kind: str
    original_filename: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    preview_url: str | None = None
    original_url: str | None = None
    poster_url: str | None = None
    download_url: str | None = None
    stream_url: str | None = None


class ArticleTocItemGet(BaseSchema):
    level: int = Field(ge=2, le=3)
    text: str
    anchor: str


class ArticleCreate(BaseSchema):
    title: str = Field(default="", max_length=300)
    body_markdown: str = Field(default="")
    status: ArticleWriteStatus = ArticleWriteStatus.DRAFT
    visibility: ArticleWriteVisibility = ArticleWriteVisibility.PRIVATE
    tags: list[str] | None = None
    cover_asset_id: uuid.UUID | None = None
    slug: str | None = Field(default=None, max_length=180)


class ArticleUpdate(BaseSchema):
    title: str | None = Field(default=None, max_length=300)
    body_markdown: str | None = None
    status: ArticleWriteStatus | None = None
    visibility: ArticleWriteVisibility | None = None
    tags: list[str] | None = None
    cover_asset_id: uuid.UUID | None = None
    slug: str | None = Field(default=None, max_length=180)


class ArticleCardGet(BaseSchema):
    article_id: uuid.UUID
    content_id: uuid.UUID
    title: str
    excerpt: str
    slug: str
    canonical_path: str
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    created_at: datetime.datetime
    updated_at: datetime.datetime
    published_at: datetime.datetime | None = None
    comments_count: int = Field(ge=0)
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    reading_time_minutes: int = Field(ge=1)
    word_count: int = Field(ge=0)
    user: UserGet
    tags: list[TagGet] = Field(default_factory=list)
    cover: ArticleAssetGet | None = None
    my_reaction: ReactionTypeEnum | None = None
    is_owner: bool


class ArticleGet(ArticleCardGet):
    body_markdown: str
    toc: list[ArticleTocItemGet] = Field(default_factory=list)
    referenced_assets: list[ArticleAssetGet] = Field(default_factory=list)


class ArticleEditorGet(ArticleGet):
    slug_editable: bool


class ArticleRating(BaseSchema):
    article_id: uuid.UUID
    likes_count: int = Field(ge=0)
    dislikes_count: int = Field(ge=0)
    my_reaction: ReactionTypeEnum | None = None
