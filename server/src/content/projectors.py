from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.articles.presentation import build_article_asset_get
from src.articles.schemas import ArticleAssetGet
from src.assets.storage import AssetStorage
from src.content.enums import ContentTypeEnum
from src.content.schemas import ContentListItemGet
from src.moments.presentation import build_moment_get
from src.posts.presentation import build_post_attachment_get
from src.users.presentation import build_user_get
from src.videos.enums import VideoProcessingStatusEnum
from src.videos.presentation import build_video_card_get


class ContentProjectorNotFound(Exception):
    pass


@dataclass(slots=True)
class ContentProjectorRegistry:
    projectors: dict[ContentTypeEnum, "BaseContentProjector"]

    def get(self, content_type: ContentTypeEnum) -> "BaseContentProjector":
        projector = self.projectors.get(content_type)
        if projector is None:
            raise ContentProjectorNotFound(f"No content projector registered for {content_type.value}")
        return projector


class BaseContentProjector:
    async def project_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
        storage: AssetStorage,
    ) -> ContentListItemGet:
        raise NotImplementedError


class PostContentProjector(BaseContentProjector):
    async def project_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
        storage: AssetStorage,
    ) -> ContentListItemGet:
        payload = await _base_payload(item, viewer_id=viewer_id, storage=storage)
        media_attachments = []
        file_attachments = []
        sorted_links = sorted(
            [
                link
                for link in getattr(item, "asset_links", [])
                if getattr(link, "deleted_at", None) is None
                and getattr(link, "attachment_type", None).value in {"media", "file"}
            ],
            key=lambda link: (
                0 if link.attachment_type.value == "media" else 1,
                link.position,
            ),
        )
        for link in sorted_links:
            attachment = await build_post_attachment_get(link, storage=storage)
            if attachment is None:
                continue
            if attachment.attachment_type.value == "media":
                media_attachments.append(attachment)
            else:
                file_attachments.append(attachment)

        return ContentListItemGet(
            **payload,
            post_content=item.post_details.body_text,
            media_attachments=media_attachments,
            file_attachments=file_attachments,
        )


class ArticleContentProjector(BaseContentProjector):
    async def project_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
        storage: AssetStorage,
    ) -> ContentListItemGet:
        payload = await _base_payload(item, viewer_id=viewer_id, storage=storage)
        cover: ArticleAssetGet | None = None
        for link in getattr(item, "asset_links", []):
            if getattr(link, "deleted_at", None) is None and link.attachment_type.value == "cover":
                cover = await build_article_asset_get(link, storage=storage)
                break

        return ContentListItemGet(
            **payload,
            title=item.title,
            excerpt=item.excerpt,
            slug=item.article_details.slug,
            canonical_path=f"/articles/{item.content_id}",
            reading_time_minutes=item.article_details.reading_time_minutes,
            word_count=item.article_details.word_count,
            cover=cover,
        )


class VideoContentProjector(BaseContentProjector):
    async def project_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
        storage: AssetStorage,
    ) -> ContentListItemGet:
        payload = await _base_payload(item, viewer_id=viewer_id, storage=storage)
        card = await build_video_card_get(item, viewer_id=viewer_id, storage=storage)
        return ContentListItemGet(
            **payload,
            title=card.title,
            description=card.description,
            excerpt=card.excerpt,
            canonical_path=card.canonical_path,
            cover=card.cover,
            duration_seconds=card.duration_seconds,
            orientation=card.orientation,
            processing_status=card.processing_status,
            processing_error=card.processing_error,
        )


class MomentContentProjector(BaseContentProjector):
    async def project_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
        storage: AssetStorage,
    ) -> ContentListItemGet:
        payload = await _base_payload(item, viewer_id=viewer_id, storage=storage)
        moment = await build_moment_get(
            item,
            viewer_id=viewer_id,
            storage=storage,
            include_playback_sources=False,
        )
        return ContentListItemGet(
            **payload,
            caption=moment.caption,
            excerpt=moment.caption,
            canonical_path=f"/moments?moment={item.content_id}",
            cover=moment.cover,
            duration_seconds=moment.duration_seconds,
            orientation=moment.orientation,
            processing_status=moment.processing_status,
            processing_error=moment.processing_error,
        )


async def _base_payload(
    item,
    *,
    viewer_id: uuid.UUID | None,
    storage: AssetStorage,
) -> dict:
    return {
        "content_id": item.content_id,
        "content_type": item.content_type,
        "status": item.status,
        "visibility": item.visibility,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "published_at": item.published_at,
        "comments_count": item.comments_count,
        "likes_count": item.likes_count,
        "dislikes_count": item.dislikes_count,
        "views_count": getattr(item, "views_count", 0),
        "user": await build_user_get(item.author, viewer_id=viewer_id, storage=storage),
        "tags": item.tags,
        "my_reaction": item.my_reaction,
        "is_owner": item.author_id == viewer_id,
    }


def build_default_content_projector_registry() -> ContentProjectorRegistry:
    return ContentProjectorRegistry(
        projectors={
            ContentTypeEnum.POST: PostContentProjector(),
            ContentTypeEnum.ARTICLE: ArticleContentProjector(),
            ContentTypeEnum.VIDEO: VideoContentProjector(),
            ContentTypeEnum.MOMENT: MomentContentProjector(),
        }
    )
