from __future__ import annotations

import datetime
import uuid

from src.articles.enums import ArticleOrder, ArticleProfileFilter, ArticleWriteStatus, ArticleWriteVisibility
from src.articles.exceptions import ArticleNotFound, InvalidArticle
from src.articles.markdown import ArticleAssetReference, analyze_article_markdown, normalize_slug, slugify_title
from src.articles.presentation import build_article_card_get, build_article_editor_get, build_article_get
from src.articles.repository import ArticleRepository
from src.articles.schemas import ArticleCardGet, ArticleCreate, ArticleEditorGet, ArticleGet, ArticleRating, ArticleUpdate
from src.assets.enums import (
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
    AttachmentTypeEnum,
)
from src.assets.models import AssetModel
from src.assets.repository import AssetRepository
from src.assets.service import AssetService
from src.assets.storage import AssetStorage
from src.common.exceptions import PermissionDenied
from src.content.access import can_view_content
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.tags.service import TagService
from src.users.schemas import UserGet


ARTICLE_ALLOWED_ASSET_STATUSES = {
    AssetStatusEnum.UPLOADED,
    AssetStatusEnum.PROCESSING,
    AssetStatusEnum.READY,
}
FORBIDDEN_USAGE_CONTEXTS = {"avatar"}
COVER_ONLY_USAGE_CONTEXTS = {"article_cover"}
INLINE_ONLY_USAGE_CONTEXTS = {"article_inline_image"}
VIDEO_ONLY_USAGE_CONTEXTS = {"article_video"}


class ArticleService:
    def __init__(
        self,
        repository: ArticleRepository,
        tag_service: TagService,
        asset_repository: AssetRepository,
        asset_service: AssetService,
        asset_storage: AssetStorage,
    ) -> None:
        self._repository = repository
        self._tag_service = tag_service
        self._asset_repository = asset_repository
        self._asset_service = asset_service
        self._asset_storage = asset_storage

    async def create_article(
        self,
        user: UserGet,
        data: ArticleCreate,
    ) -> ArticleGet:
        payload = data.model_dump()
        title = payload["title"].strip()
        body_markdown = payload["body_markdown"]
        cover_asset_id = payload["cover_asset_id"]
        tags = self._tag_service.normalize_tags(data.tags)
        self._ensure_article_has_content(
            title=title,
            body_markdown=body_markdown,
            cover_asset_id=cover_asset_id,
        )

        analysis = analyze_article_markdown(body_markdown)
        status = self._map_status(data.status)
        visibility = self._map_visibility(data.visibility)
        self._validate_publishable_payload(
            title=title,
            body_markdown=body_markdown,
            status=status,
        )

        slug = normalize_slug(data.slug) if data.slug else slugify_title(title)
        now = self._now()
        attachments = await self._validate_and_prepare_assets(
            owner_id=user.user_id,
            cover_asset_id=cover_asset_id,
            asset_references=analysis.asset_references,
        )

        article = await self._repository.create(
            author_id=user.user_id,
            title=title,
            excerpt=analysis.excerpt,
            body_markdown=body_markdown,
            slug=slug,
            word_count=analysis.word_count,
            reading_time_minutes=analysis.reading_time_minutes,
            toc=analysis.toc,
            seo_title=self._normalize_nullable_text(data.seo_title),
            seo_description=self._normalize_nullable_text(data.seo_description),
            status=status,
            visibility=visibility,
            created_at=now,
            updated_at=now,
            published_at=now if status == ContentStatusEnum.PUBLISHED else None,
            commit=False,
        )
        if attachments:
            await self._repository.replace_asset_links(
                content_id=article.content_id,
                attachments=attachments,
                commit=False,
            )
        if tags:
            resolved_tags = await self._tag_service.resolve_tags(tags)
            await self._tag_service.replace_content_tags(
                content_id=article.content_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()
        article = await self._repository.get_single(content_id=article.content_id, viewer_id=user.user_id)
        if article is None:
            raise ArticleNotFound("Created article is unavailable")
        return await self._build_article_get(article, viewer_id=user.user_id)

    async def get_article(
        self,
        article_id: uuid.UUID,
        user: UserGet | None = None,
    ) -> ArticleGet:
        viewer_id = user.user_id if user else None
        article = await self._repository.get_single(content_id=article_id, viewer_id=viewer_id)
        if article is None or not self._can_view_article(article=article, viewer_id=viewer_id):
            raise ArticleNotFound(f"Article with id {article_id!s} not found")
        return await self._build_article_get(article, viewer_id=viewer_id)

    async def get_article_editor(
        self,
        article_id: uuid.UUID,
        user: UserGet,
    ) -> ArticleEditorGet:
        article = await self._repository.get_single(content_id=article_id, viewer_id=user.user_id)
        if article is None or article.author_id != user.user_id or article.deleted_at is not None:
            raise ArticleNotFound(f"Article with id {article_id!s} not found")
        return await self._build_article_editor_get(article, viewer_id=user.user_id)

    async def get_articles(
        self,
        order: ArticleOrder,
        desc: bool,
        offset: int,
        limit: int,
        user_id: uuid.UUID | None = None,
        user: UserGet | None = None,
        profile_filter: ArticleProfileFilter = ArticleProfileFilter.PUBLIC,
    ) -> list[ArticleCardGet]:
        viewer_id = user.user_id if user else None
        if user_id is None:
            articles = await self._repository.get_feed(
                viewer_id=viewer_id,
                order=order,
                order_desc=desc,
                offset=offset,
                limit=limit,
            )
        else:
            articles = await self._repository.get_author_articles(
                author_id=user_id,
                viewer_id=viewer_id,
                profile_filter=profile_filter,
                order=order,
                order_desc=desc,
                offset=offset,
                limit=limit,
            )
        return [await build_article_card_get(article, viewer_id=viewer_id, storage=self._asset_storage) for article in articles]

    async def update_article(
        self,
        user: UserGet,
        article_id: uuid.UUID,
        data: ArticleUpdate,
    ) -> ArticleGet:
        article = await self._repository.get_single(content_id=article_id, viewer_id=user.user_id)
        if article is None or article.author_id != user.user_id:
            raise PermissionDenied(f"User with id {user.user_id} can't edit article with id {article_id}")
        if article.status == ContentStatusEnum.DELETED:
            raise ArticleNotFound(f"Article with id {article_id!s} not found")

        payload = data.model_dump(exclude_unset=True)
        next_title = payload.get("title", article.title or "").strip()
        next_body = payload.get("body_markdown", article.article_details.body_markdown)
        next_cover = payload["cover_asset_id"] if "cover_asset_id" in payload else self._current_cover_asset_id(article)
        next_status = self._map_status(payload["status"]) if "status" in payload else article.status
        next_visibility = (
            self._map_visibility(payload["visibility"])
            if "visibility" in payload
            else article.visibility
        )
        next_tags = self._tag_service.normalize_tags(payload["tags"]) if "tags" in payload else None
        next_seo_title = (
            self._normalize_nullable_text(payload["seo_title"])
            if "seo_title" in payload
            else article.article_details.seo_title
        )
        next_seo_description = (
            self._normalize_nullable_text(payload["seo_description"])
            if "seo_description" in payload
            else article.article_details.seo_description
        )
        if "slug" in payload:
            if article.published_at is not None:
                raise InvalidArticle("Article slug cannot be changed after publication")
            next_slug = normalize_slug(payload["slug"]) if payload["slug"] else slugify_title(next_title)
        elif article.published_at is None:
            next_slug = slugify_title(next_title)
        else:
            next_slug = article.article_details.slug

        self._ensure_article_has_content(
            title=next_title,
            body_markdown=next_body,
            cover_asset_id=next_cover,
        )
        analysis = analyze_article_markdown(next_body)
        self._validate_publishable_payload(
            title=next_title,
            body_markdown=next_body,
            status=next_status,
        )
        next_attachments = await self._validate_and_prepare_assets(
            owner_id=user.user_id,
            cover_asset_id=next_cover,
            asset_references=analysis.asset_references,
        )

        updated_at = self._now()
        published_at = article.published_at
        if next_status == ContentStatusEnum.PUBLISHED and published_at is None:
            published_at = updated_at
        previous_attachment_asset_ids = await self._repository.get_attachment_asset_ids(content_id=article_id)
        await self._repository.update_article(
            content_id=article_id,
            title=next_title,
            excerpt=analysis.excerpt,
            body_markdown=next_body,
            slug=next_slug,
            word_count=analysis.word_count,
            reading_time_minutes=analysis.reading_time_minutes,
            toc=analysis.toc,
            seo_title=next_seo_title,
            seo_description=next_seo_description,
            status=next_status,
            visibility=next_visibility,
            updated_at=updated_at,
            published_at=published_at,
            commit=False,
        )
        await self._repository.replace_asset_links(
            content_id=article_id,
            attachments=next_attachments,
            commit=False,
        )
        if next_tags is not None:
            resolved_tags = await self._tag_service.resolve_tags(next_tags)
            await self._tag_service.replace_content_tags(
                content_id=article_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()
        next_attachment_asset_ids = {attachment["asset_id"] for attachment in next_attachments}
        await self._mark_assets_orphaned(
            asset_ids=previous_attachment_asset_ids - next_attachment_asset_ids
        )

        updated_article = await self._repository.get_single(content_id=article_id, viewer_id=user.user_id)
        if updated_article is None:
            raise ArticleNotFound(f"Article with id {article_id!s} not found")
        return await self._build_article_get(updated_article, viewer_id=user.user_id)

    async def delete_article(
        self,
        user: UserGet,
        article_id: uuid.UUID,
    ) -> None:
        article = await self._repository.get_single(content_id=article_id, viewer_id=user.user_id)
        if article is None or article.author_id != user.user_id:
            raise PermissionDenied(f"User with id {user.user_id} can't delete article with id {article_id}")
        if article.status == ContentStatusEnum.DELETED:
            return

        attachment_asset_ids = await self._repository.get_attachment_asset_ids(content_id=article_id)
        now = self._now()
        await self._repository.soft_delete_article(
            content_id=article_id,
            updated_at=now,
            deleted_at=now,
            commit=False,
        )
        await self._repository.replace_asset_links(
            content_id=article_id,
            attachments=[],
            commit=False,
        )
        await self._repository.commit()
        await self._mark_assets_orphaned(asset_ids=attachment_asset_ids)

    async def add_like_to_article(
        self,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ArticleRating:
        return await self._set_reaction(
            article_id=article_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.LIKE,
        )

    async def remove_like_from_article(
        self,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ArticleRating:
        return await self._remove_reaction(
            article_id=article_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.LIKE,
        )

    async def add_dislike_to_article(
        self,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ArticleRating:
        return await self._set_reaction(
            article_id=article_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.DISLIKE,
        )

    async def remove_dislike_from_article(
        self,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ArticleRating:
        return await self._remove_reaction(
            article_id=article_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.DISLIKE,
        )

    async def _set_reaction(
        self,
        *,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> ArticleRating:
        await self._get_reactable_article(article_id=article_id, viewer_id=user_id)
        await self._repository.set_reaction(
            content_id=article_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        return await self._build_rating(article_id=article_id, viewer_id=user_id)

    async def _remove_reaction(
        self,
        *,
        article_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> ArticleRating:
        await self._get_reactable_article(article_id=article_id, viewer_id=user_id)
        await self._repository.remove_reaction(
            content_id=article_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        return await self._build_rating(article_id=article_id, viewer_id=user_id)

    async def _build_rating(
        self,
        *,
        article_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> ArticleRating:
        article = await self._repository.get_single(content_id=article_id, viewer_id=viewer_id)
        if article is None:
            raise ArticleNotFound(f"Article with id {article_id!s} not found")
        return ArticleRating(
            article_id=article.content_id,
            likes_count=article.likes_count,
            dislikes_count=article.dislikes_count,
            my_reaction=article.my_reaction,
        )

    async def _get_reactable_article(
        self,
        *,
        article_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        article = await self._repository.get_single(content_id=article_id, viewer_id=viewer_id)
        if article is None or not self._can_view_article(article=article, viewer_id=viewer_id):
            raise ArticleNotFound(f"Article with id {article_id!s} not found")
        if article.status != ContentStatusEnum.PUBLISHED:
            raise ArticleNotFound(f"Article with id {article_id!s} not found")
        return article

    async def _validate_and_prepare_assets(
        self,
        *,
        owner_id: uuid.UUID,
        cover_asset_id: uuid.UUID | None,
        asset_references: list[ArticleAssetReference],
    ) -> list[dict[str, object]]:
        asset_ids = []
        if cover_asset_id is not None:
            asset_ids.append(cover_asset_id)
        asset_ids.extend(reference.asset_id for reference in asset_references)

        assets = await self._asset_repository.get_assets(
            asset_ids=asset_ids,
            owner_id=owner_id,
        )
        assets_by_id = {asset.asset_id: asset for asset in assets}
        missing_asset_ids = [asset_id for asset_id in asset_ids if asset_id not in assets_by_id]
        if missing_asset_ids:
            raise InvalidArticle(
                "Some article assets are unavailable for this user: "
                + ", ".join(str(asset_id) for asset_id in missing_asset_ids)
            )

        attachments: list[dict[str, object]] = []
        seen_asset_pairs: set[tuple[uuid.UUID, str]] = set()
        if cover_asset_id is not None:
            cover_asset = assets_by_id[cover_asset_id]
            self._validate_article_asset(
                asset=cover_asset,
                attachment_type=AttachmentTypeEnum.COVER,
            )
            seen_asset_pairs.add((cover_asset_id, AttachmentTypeEnum.COVER.value))
            attachments.append(
                {
                    "asset_id": cover_asset_id,
                    "attachment_type": AttachmentTypeEnum.COVER,
                    "position": 0,
                }
            )

        inline_position = 0
        video_position = 0
        for reference in asset_references:
            attachment_type = (
                AttachmentTypeEnum.INLINE
                if reference.attachment_type == AttachmentTypeEnum.INLINE.value
                else AttachmentTypeEnum.VIDEO_SOURCE
            )
            pair = (reference.asset_id, attachment_type.value)
            if pair in seen_asset_pairs:
                raise InvalidArticle("The same asset cannot be attached twice in the same article placement")
            seen_asset_pairs.add(pair)

            asset = assets_by_id[reference.asset_id]
            self._validate_article_asset(
                asset=asset,
                attachment_type=attachment_type,
            )
            position = inline_position if attachment_type == AttachmentTypeEnum.INLINE else video_position
            attachments.append(
                {
                    "asset_id": reference.asset_id,
                    "attachment_type": attachment_type,
                    "position": position,
                }
            )
            if attachment_type == AttachmentTypeEnum.INLINE:
                inline_position += 1
            else:
                video_position += 1

        return attachments

    def _validate_article_asset(
        self,
        *,
        asset: AssetModel,
        attachment_type: AttachmentTypeEnum,
    ) -> None:
        if asset.status not in ARTICLE_ALLOWED_ASSET_STATUSES:
            raise InvalidArticle(f"Asset {asset.asset_id} is not ready to be attached to an article")

        usage_context = (asset.asset_metadata or {}).get("usage_context")
        if usage_context in FORBIDDEN_USAGE_CONTEXTS:
            raise InvalidArticle(f"Asset {asset.asset_id} cannot be reused as an article asset")
        if usage_context in COVER_ONLY_USAGE_CONTEXTS and attachment_type != AttachmentTypeEnum.COVER:
            raise InvalidArticle(f"Asset {asset.asset_id} must stay as an article cover")
        if usage_context in INLINE_ONLY_USAGE_CONTEXTS and attachment_type != AttachmentTypeEnum.INLINE:
            raise InvalidArticle(f"Asset {asset.asset_id} must stay as an inline article image")
        if usage_context in VIDEO_ONLY_USAGE_CONTEXTS and attachment_type != AttachmentTypeEnum.VIDEO_SOURCE:
            raise InvalidArticle(f"Asset {asset.asset_id} must stay as an inline article video")

        original_variant = next(
            (
                variant
                for variant in asset.variants
                if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL
            ),
            None,
        )
        if original_variant is None or original_variant.status != AssetVariantStatusEnum.READY:
            raise InvalidArticle(f"Asset {asset.asset_id} original file is not available yet")

        if attachment_type in {AttachmentTypeEnum.COVER, AttachmentTypeEnum.INLINE} and asset.asset_type != AssetTypeEnum.IMAGE:
            raise InvalidArticle("Article covers and inline assets must be images")
        if attachment_type == AttachmentTypeEnum.VIDEO_SOURCE and asset.asset_type != AssetTypeEnum.VIDEO:
            raise InvalidArticle("Video directives must reference uploaded video assets")

    def _ensure_article_has_content(
        self,
        *,
        title: str,
        body_markdown: str,
        cover_asset_id: uuid.UUID | None,
    ) -> None:
        if title or body_markdown.strip() or cover_asset_id is not None:
            return
        raise InvalidArticle("Article draft must contain at least a title, body, or cover")

    def _validate_publishable_payload(
        self,
        *,
        title: str,
        body_markdown: str,
        status: ContentStatusEnum,
    ) -> None:
        if status != ContentStatusEnum.PUBLISHED:
            return
        if not title:
            raise InvalidArticle("Published article must have a title")
        if not body_markdown.strip():
            raise InvalidArticle("Published article must have a body")

    async def _mark_assets_orphaned(
        self,
        *,
        asset_ids: set[uuid.UUID],
    ) -> None:
        for asset_id in asset_ids:
            await self._asset_service.mark_asset_orphaned_if_unreferenced(asset_id=asset_id)

    async def _build_article_get(
        self,
        article,
        *,
        viewer_id: uuid.UUID | None,
    ) -> ArticleGet:
        return await build_article_get(article, viewer_id=viewer_id, storage=self._asset_storage)

    async def _build_article_editor_get(
        self,
        article,
        *,
        viewer_id: uuid.UUID | None,
    ) -> ArticleEditorGet:
        return await build_article_editor_get(article, viewer_id=viewer_id, storage=self._asset_storage)

    def _current_cover_asset_id(self, article) -> uuid.UUID | None:  # type: ignore[no-untyped-def]
        for link in getattr(article, "asset_links", []):
            if link.deleted_at is None and link.attachment_type == AttachmentTypeEnum.COVER:
                return link.asset_id
        return None

    def _can_view_article(
        self,
        *,
        article,
        viewer_id: uuid.UUID | None,
    ) -> bool:
        return can_view_content(content=article, viewer_id=viewer_id)

    def _map_status(self, status: ArticleWriteStatus) -> ContentStatusEnum:
        mapping = {
            ArticleWriteStatus.DRAFT: ContentStatusEnum.DRAFT,
            ArticleWriteStatus.PUBLISHED: ContentStatusEnum.PUBLISHED,
        }
        return mapping[status]

    def _map_visibility(self, visibility: ArticleWriteVisibility) -> ContentVisibilityEnum:
        mapping = {
            ArticleWriteVisibility.PUBLIC: ContentVisibilityEnum.PUBLIC,
            ArticleWriteVisibility.PRIVATE: ContentVisibilityEnum.PRIVATE,
        }
        return mapping[visibility]

    def _normalize_nullable_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
