from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

from src.assets.enums import (
    AttachmentTypeEnum,
    AssetStatusEnum,
    AssetTypeEnum,
    AssetVariantStatusEnum,
    AssetVariantTypeEnum,
)
from src.assets.models import AssetModel
from src.assets.repository import AssetRepository
from src.assets.service import AssetService
from src.assets.storage import AssetStorage
from src.common.exceptions import PermissionDenied
from src.content.access import can_view_content
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.posts.enums import PostOrder, PostProfileFilter, PostWriteStatus, PostWriteVisibility
from src.posts.exceptions import InvalidPost, PostNotFound
from src.posts.presentation import build_post_get
from src.posts.repository import PostRepository
from src.posts.schemas import PostAttachmentWrite, PostCreate, PostGet, PostRating, PostUpdate
from src.tags.service import TagService
from src.users.schemas import UserGet

if TYPE_CHECKING:
    from src.activity.service import ActivityService


POST_MEDIA_LIMIT = 30
POST_FILE_LIMIT = 10
POST_ATTACHMENT_ALLOWED_STATUSES = {
    AssetStatusEnum.UPLOADED,
    AssetStatusEnum.PROCESSING,
    AssetStatusEnum.READY,
}
FORBIDDEN_USAGE_CONTEXTS = {"avatar"}
MEDIA_ONLY_USAGE_CONTEXTS = {"post_media"}
FILE_ONLY_USAGE_CONTEXTS = {"post_file"}


class PostService:
    def __init__(
        self,
        repository: PostRepository,
        tag_service: TagService,
        asset_repository: AssetRepository,
        asset_service: AssetService,
        asset_storage: AssetStorage,
        activity_service: ActivityService | None = None,
    ) -> None:
        self._repository = repository
        self._tag_service = tag_service
        self._asset_repository = asset_repository
        self._asset_service = asset_service
        self._asset_storage = asset_storage
        self._activity_service = activity_service

    async def create_post(
        self,
        user: UserGet,
        data: PostCreate,
    ) -> PostGet:
        now = self._now()
        status = self._map_status(data.status)
        visibility = self._map_visibility(data.visibility)
        tags = self._tag_service.normalize_tags(data.tags)
        content = data.content or ""
        attachments = await self._validate_and_prepare_attachments(
            owner_id=user.user_id,
            attachments=data.attachments,
        )
        self._ensure_post_has_content(
            text_content=content,
            attachments=data.attachments,
        )

        post = await self._repository.create(
            author_id=user.user_id,
            body_text=content,
            status=status,
            visibility=visibility,
            created_at=now,
            updated_at=now,
            published_at=now if status == ContentStatusEnum.PUBLISHED else None,
            commit=False,
        )
        if attachments:
            await self._repository.replace_attachments(
                content_id=post.content_id,
                attachments=attachments,
                commit=False,
            )
        if tags:
            resolved_tags = await self._tag_service.resolve_tags(tags)
            await self._tag_service.replace_content_tags(
                content_id=post.content_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()
        post = await self._repository.get_single(content_id=post.content_id, viewer_id=user.user_id)
        if post is None:
            raise PostNotFound("Created post is unavailable")
        post.is_owner = True
        return await self._build_post_get(post, viewer_id=user.user_id)

    async def get_post(
        self,
        post_id: uuid.UUID,
        user: UserGet | None = None,
    ) -> PostGet:
        viewer_id = user.user_id if user else None
        post = await self._repository.get_single(content_id=post_id, viewer_id=viewer_id)
        if post is None or not self._can_view_post(post=post, viewer_id=viewer_id):
            raise PostNotFound(f"Post with id {post_id!s} not found")

        return await self._build_post_get(post, viewer_id=viewer_id)

    async def get_posts(
        self,
        order: PostOrder,
        desc: bool,
        offset: int,
        limit: int,
        user_id: uuid.UUID | None = None,
        user: UserGet | None = None,
        profile_filter: PostProfileFilter = PostProfileFilter.PUBLIC,
    ) -> list[PostGet]:
        viewer_id = user.user_id if user else None

        if user_id is None:
            posts = await self._repository.get_feed(
                viewer_id=viewer_id,
                order=order,
                order_desc=desc,
                offset=offset,
                limit=limit,
            )
        else:
            posts = await self._repository.get_author_posts(
                author_id=user_id,
                viewer_id=viewer_id,
                profile_filter=profile_filter,
                order=order,
                order_desc=desc,
                offset=offset,
                limit=limit,
            )

        return [await self._build_post_get(post, viewer_id=viewer_id) for post in posts]

    async def update_post(
        self,
        user: UserGet,
        post_id: uuid.UUID,
        data: PostUpdate,
    ) -> PostGet:
        post = await self._repository.get_single(content_id=post_id, viewer_id=user.user_id)
        if post is None:
            raise PermissionDenied(
                f"User with id {user.user_id} can't edit post with id {post_id}"
            )
        if post.author_id != user.user_id:
            raise PermissionDenied(
                f"User with id {user.user_id} can't edit post with id {post_id}"
            )
        if post.status == ContentStatusEnum.DELETED:
            raise PostNotFound(f"Post with id {post_id!s} not found")

        payload = data.model_dump(exclude_none=True)
        next_tags = self._tag_service.normalize_tags(payload["tags"]) if "tags" in payload else None
        next_status = self._map_status(payload["status"]) if "status" in payload else post.status
        next_visibility = (
            self._map_visibility(payload["visibility"])
            if "visibility" in payload
            else post.visibility
        )
        next_content = payload.get("content", post.post_details.body_text)
        next_attachment_input = (
            data.attachments
            if "attachments" in payload
            else self._build_current_attachment_input(post)
        )
        next_attachments = await self._validate_and_prepare_attachments(
            owner_id=user.user_id,
            attachments=next_attachment_input,
        )
        self._ensure_post_has_content(
            text_content=next_content,
            attachments=next_attachment_input,
        )

        updated_at = self._now()
        published_at = post.published_at
        if next_status == ContentStatusEnum.PUBLISHED and published_at is None:
            published_at = updated_at
        if next_status == ContentStatusEnum.DRAFT:
            published_at = None

        previous_attachment_asset_ids = await self._repository.get_attachment_asset_ids(content_id=post_id)
        await self._repository.update_post(
            content_id=post_id,
            body_text=next_content,
            status=next_status,
            visibility=next_visibility,
            updated_at=updated_at,
            published_at=published_at,
            commit=False,
        )
        if "attachments" in payload:
            await self._repository.replace_attachments(
                content_id=post_id,
                attachments=next_attachments,
                commit=False,
            )
        if next_tags is not None:
            resolved_tags = await self._tag_service.resolve_tags(next_tags)
            await self._tag_service.replace_content_tags(
                content_id=post_id,
                tag_ids=[tag.tag_id for tag in resolved_tags],
                commit=False,
            )
        await self._repository.commit()

        if "attachments" in payload:
            next_attachment_asset_ids = {attachment["asset_id"] for attachment in next_attachments}
            await self._mark_assets_orphaned(
                asset_ids=previous_attachment_asset_ids - next_attachment_asset_ids
            )

        updated_post = await self._repository.get_single(content_id=post_id, viewer_id=user.user_id)
        if updated_post is None:
            raise PostNotFound(f"Post with id {post_id!s} not found")
        return await self._build_post_get(updated_post, viewer_id=user.user_id)

    async def delete_post(
        self,
        user: UserGet,
        post_id: uuid.UUID,
    ) -> None:
        post = await self._repository.get_single(content_id=post_id, viewer_id=user.user_id)
        if post is None or post.author_id != user.user_id:
            raise PermissionDenied(
                f"User with id {user.user_id} can't delete post with id {post_id}"
            )
        if post.status == ContentStatusEnum.DELETED:
            return

        attachment_asset_ids = await self._repository.get_attachment_asset_ids(content_id=post_id)
        now = self._now()
        await self._repository.soft_delete_post(
            content_id=post_id,
            updated_at=now,
            deleted_at=now,
            commit=False,
        )
        await self._repository.replace_attachments(
            content_id=post_id,
            attachments=[],
            commit=False,
        )
        await self._repository.commit()
        await self._mark_assets_orphaned(asset_ids=attachment_asset_ids)

    async def add_like_to_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        return await self._set_reaction(
            post_id=post_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.LIKE,
        )

    async def remove_like_from_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        return await self._remove_reaction(
            post_id=post_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.LIKE,
        )

    async def add_dislike_to_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        return await self._set_reaction(
            post_id=post_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.DISLIKE,
        )

    async def remove_dislike_from_post(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PostRating:
        return await self._remove_reaction(
            post_id=post_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.DISLIKE,
        )

    async def get_user_subscriptions_posts(
        self,
        user_id: uuid.UUID,
        order: PostOrder,
        desc: bool,
        offset: int,
        limit: int,
    ) -> list[PostGet]:
        posts = await self._repository.get_user_subscriptions_posts(
            user_id=user_id,
            order=order,
            order_desc=desc,
            offset=offset,
            limit=limit,
        )
        return [await self._build_post_get(post, viewer_id=user_id) for post in posts]

    async def _set_reaction(
        self,
        *,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> PostRating:
        post = await self._get_reactable_post(post_id=post_id, viewer_id=user_id)
        result = await self._repository.set_reaction(
            content_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        if self._activity_service is not None and getattr(result, "changed", False):
            await self._activity_service.log_content_reaction(
                user_id=user_id,
                content_id=post_id,
                content_type=post.content_type,
                previous_reaction=result.previous_reaction,
                new_reaction=result.new_reaction,
            )
        return await self._build_rating(post_id=post_id, viewer_id=user_id)

    async def _remove_reaction(
        self,
        *,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> PostRating:
        post = await self._get_reactable_post(post_id=post_id, viewer_id=user_id)
        result = await self._repository.remove_reaction(
            content_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        if (
            self._activity_service is not None
            and getattr(result, "removed", False)
            and result.previous_reaction is not None
        ):
            await self._activity_service.log_content_reaction_removed(
                user_id=user_id,
                content_id=post_id,
                content_type=post.content_type,
                previous_reaction=result.previous_reaction,
            )
        return await self._build_rating(post_id=post_id, viewer_id=user_id)

    async def _build_rating(
        self,
        *,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> PostRating:
        post = await self._repository.get_single(content_id=post_id, viewer_id=viewer_id)
        if post is None:
            raise PostNotFound(f"Post with id {post_id!s} not found")

        return PostRating(
            post_id=post.content_id,
            likes_count=post.likes_count,
            dislikes_count=post.dislikes_count,
            my_reaction=post.my_reaction,
        )

    async def _get_reactable_post(
        self,
        *,
        post_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        post = await self._repository.get_single(content_id=post_id, viewer_id=viewer_id)
        if post is None or not self._can_view_post(post=post, viewer_id=viewer_id):
            raise PostNotFound(f"Post with id {post_id!s} not found")
        if post.status != ContentStatusEnum.PUBLISHED:
            raise PostNotFound(f"Post with id {post_id!s} not found")

        return post

    async def _validate_and_prepare_attachments(
        self,
        *,
        owner_id: uuid.UUID,
        attachments: list[PostAttachmentWrite],
    ) -> list[dict[str, object]]:
        self._validate_attachment_payload(attachments)
        asset_ids = [attachment.asset_id for attachment in attachments]
        assets = await self._asset_repository.get_assets(
            asset_ids=asset_ids,
            owner_id=owner_id,
        )
        assets_by_id = {asset.asset_id: asset for asset in assets}
        missing_asset_ids = [asset_id for asset_id in asset_ids if asset_id not in assets_by_id]
        if missing_asset_ids:
            raise InvalidPost(
                f"Some attachments are unavailable for this user: {', '.join(str(asset_id) for asset_id in missing_asset_ids)}"
            )

        records: list[dict[str, object]] = []
        for attachment in attachments:
            asset = assets_by_id[attachment.asset_id]
            self._validate_attachment_asset(asset=asset, attachment=attachment)
            records.append(
                {
                    "asset_id": attachment.asset_id,
                    "attachment_type": attachment.attachment_type,
                    "position": attachment.position,
                }
            )
        return records

    def _validate_attachment_payload(
        self,
        attachments: list[PostAttachmentWrite],
    ) -> None:
        seen_asset_ids: set[uuid.UUID] = set()
        grouped_positions: dict[AttachmentTypeEnum, list[int]] = {
            AttachmentTypeEnum.MEDIA: [],
            AttachmentTypeEnum.FILE: [],
        }

        for attachment in attachments:
            if attachment.attachment_type not in grouped_positions:
                raise InvalidPost(f"Attachment type {attachment.attachment_type.value} is not allowed for posts")
            if attachment.asset_id in seen_asset_ids:
                raise InvalidPost(f"Asset {attachment.asset_id} cannot be attached more than once to the same post")
            seen_asset_ids.add(attachment.asset_id)
            grouped_positions[attachment.attachment_type].append(attachment.position)

        if len(grouped_positions[AttachmentTypeEnum.MEDIA]) > POST_MEDIA_LIMIT:
            raise InvalidPost(f"Post cannot contain more than {POST_MEDIA_LIMIT} media attachments")
        if len(grouped_positions[AttachmentTypeEnum.FILE]) > POST_FILE_LIMIT:
            raise InvalidPost(f"Post cannot contain more than {POST_FILE_LIMIT} file attachments")

        for attachment_type, positions in grouped_positions.items():
            if sorted(positions) != list(range(len(positions))):
                raise InvalidPost(
                    f"{attachment_type.value.capitalize()} attachment positions must be contiguous and start at 0"
                )

    def _validate_attachment_asset(
        self,
        *,
        asset: AssetModel,
        attachment: PostAttachmentWrite,
    ) -> None:
        if asset.status not in POST_ATTACHMENT_ALLOWED_STATUSES:
            raise InvalidPost(f"Asset {asset.asset_id} is not ready to be attached to a post")

        usage_context = (asset.asset_metadata or {}).get("usage_context")
        if usage_context in FORBIDDEN_USAGE_CONTEXTS:
            raise InvalidPost(f"Asset {asset.asset_id} cannot be reused as a post attachment")
        if usage_context in MEDIA_ONLY_USAGE_CONTEXTS and attachment.attachment_type != AttachmentTypeEnum.MEDIA:
            raise InvalidPost(f"Asset {asset.asset_id} must stay in the media attachment block")
        if usage_context in FILE_ONLY_USAGE_CONTEXTS and attachment.attachment_type != AttachmentTypeEnum.FILE:
            raise InvalidPost(f"Asset {asset.asset_id} must stay in the file attachment block")

        original_variant = next(
            (
                variant
                for variant in asset.variants
                if variant.asset_variant_type == AssetVariantTypeEnum.ORIGINAL
            ),
            None,
        )
        if original_variant is None:
            raise InvalidPost(f"Asset {asset.asset_id} has no original file available")
        if original_variant.status != AssetVariantStatusEnum.READY:
            raise InvalidPost(f"Asset {asset.asset_id} original file is not available yet")

        if attachment.attachment_type == AttachmentTypeEnum.MEDIA and asset.asset_type not in {
            AssetTypeEnum.IMAGE,
            AssetTypeEnum.VIDEO,
        }:
            raise InvalidPost("Media attachments must be images or videos")

    def _ensure_post_has_content(
        self,
        *,
        text_content: str,
        attachments: list[PostAttachmentWrite],
    ) -> None:
        if text_content.strip() or attachments:
            return
        raise InvalidPost("Post must contain at least text, media, or files")

    async def _mark_assets_orphaned(
        self,
        *,
        asset_ids: set[uuid.UUID],
    ) -> None:
        for asset_id in asset_ids:
            await self._asset_service.mark_asset_orphaned_if_unreferenced(asset_id=asset_id)

    def _build_current_attachment_input(self, post) -> list[PostAttachmentWrite]:  # type: ignore[no-untyped-def]
        links = sorted(
            [
                link
                for link in getattr(post, "asset_links", [])
                if link.deleted_at is None
                and link.attachment_type in {AttachmentTypeEnum.MEDIA, AttachmentTypeEnum.FILE}
            ],
            key=lambda link: (0 if link.attachment_type == AttachmentTypeEnum.MEDIA else 1, link.position),
        )
        return [
            PostAttachmentWrite(
                asset_id=link.asset_id,
                attachment_type=link.attachment_type,
                position=link.position,
            )
            for link in links
        ]

    def _can_view_post(
        self,
        *,
        post,
        viewer_id: uuid.UUID | None,
    ) -> bool:
        return can_view_content(content=post, viewer_id=viewer_id)

    def _map_status(self, status: PostWriteStatus) -> ContentStatusEnum:
        return ContentStatusEnum(status.value)

    def _map_visibility(self, visibility: PostWriteVisibility) -> ContentVisibilityEnum:
        return ContentVisibilityEnum(visibility.value)

    async def _build_post_get(
        self,
        post,
        *,
        viewer_id: uuid.UUID | None,
    ) -> PostGet:
        return await build_post_get(
            post,
            viewer_id=viewer_id,
            storage=self._asset_storage,
        )

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
