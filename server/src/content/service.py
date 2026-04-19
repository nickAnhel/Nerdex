from __future__ import annotations

import uuid

from src.articles.presentation import build_article_asset_get
from src.articles.schemas import ArticleAssetGet
from src.assets.storage import AssetStorage
from src.content.enums import ContentTypeEnum
from src.content.enums_list import ContentOrder
from src.content.repository import ContentRepository
from src.content.schemas import ContentListItemGet
from src.posts.presentation import build_post_attachment_get
from src.users.presentation import build_user_get


class ContentService:
    def __init__(
        self,
        repository: ContentRepository,
        asset_storage: AssetStorage,
    ) -> None:
        self._repository = repository
        self._asset_storage = asset_storage

    async def get_feed(
        self,
        *,
        order: ContentOrder,
        desc: bool,
        offset: int,
        limit: int,
        viewer_id: uuid.UUID | None,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_feed(
            viewer_id=viewer_id,
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=viewer_id) for item in content_items]

    async def get_subscriptions_feed(
        self,
        *,
        user_id: uuid.UUID,
        order: ContentOrder,
        desc: bool,
        offset: int,
        limit: int,
    ) -> list[ContentListItemGet]:
        content_items = await self._repository.get_user_subscriptions_feed(
            user_id=user_id,
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_feed_item(item, viewer_id=user_id) for item in content_items]

    async def _build_feed_item(
        self,
        item,
        *,
        viewer_id: uuid.UUID | None,
    ) -> ContentListItemGet:
        payload = {
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
            "user": await build_user_get(item.author, viewer_id=viewer_id, storage=self._asset_storage),
            "tags": item.tags,
            "my_reaction": item.my_reaction,
            "is_owner": item.author_id == viewer_id,
        }

        if item.content_type == ContentTypeEnum.POST:
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
                attachment = await build_post_attachment_get(link, storage=self._asset_storage)
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

        cover: ArticleAssetGet | None = None
        for link in getattr(item, "asset_links", []):
            if getattr(link, "deleted_at", None) is None and link.attachment_type.value == "cover":
                cover = await build_article_asset_get(link, storage=self._asset_storage)
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
