from __future__ import annotations

import datetime
import uuid

from src.common.exceptions import PermissionDenied
from src.content.access import can_view_content
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.posts.enums import PostOrder, PostProfileFilter, PostWriteStatus, PostWriteVisibility
from src.posts.exceptions import PostNotFound
from src.posts.repository import PostRepository
from src.posts.schemas import PostCreate, PostGet, PostRating, PostUpdate
from src.tags.service import TagService
from src.users.schemas import UserGet


class PostService:
    def __init__(
        self,
        repository: PostRepository,
        tag_service: TagService,
    ) -> None:
        self._repository = repository
        self._tag_service = tag_service

    async def create_post(
        self,
        user: UserGet,
        data: PostCreate,
    ) -> PostGet:
        now = self._now()
        status = self._map_status(data.status)
        visibility = self._map_visibility(data.visibility)
        tags = self._tag_service.normalize_tags(data.tags)

        post = await self._repository.create(
            author_id=user.user_id,
            body_text=data.content,
            status=status,
            visibility=visibility,
            created_at=now,
            updated_at=now,
            published_at=now if status == ContentStatusEnum.PUBLISHED else None,
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
        return PostGet.model_validate(post)

    async def get_post(
        self,
        post_id: uuid.UUID,
        user: UserGet | None = None,
    ) -> PostGet:
        viewer_id = user.user_id if user else None
        post = await self._repository.get_single(content_id=post_id, viewer_id=viewer_id)
        if post is None or not self._can_view_post(post=post, viewer_id=viewer_id):
            raise PostNotFound(f"Post with id {post_id!s} not found")

        return PostGet.model_validate(post)

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

        return [PostGet.model_validate(post) for post in posts]

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
        next_tags = (
            self._tag_service.normalize_tags(payload["tags"])
            if "tags" in payload
            else None
        )
        next_status = self._map_status(payload["status"]) if "status" in payload else post.status
        next_visibility = (
            self._map_visibility(payload["visibility"])
            if "visibility" in payload
            else post.visibility
        )
        next_content = payload.get("content", post.post_details.body_text)

        updated_at = self._now()
        published_at = post.published_at
        if next_status == ContentStatusEnum.PUBLISHED and published_at is None:
            published_at = updated_at
        if next_status == ContentStatusEnum.DRAFT:
            published_at = None

        updated_post = await self._repository.update_post(
            content_id=post_id,
            body_text=next_content,
            status=next_status,
            visibility=next_visibility,
            updated_at=updated_at,
            published_at=published_at,
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
        updated_post = await self._repository.get_single(content_id=post_id, viewer_id=user.user_id)
        if updated_post is None:
            raise PostNotFound(f"Post with id {post_id!s} not found")
        return PostGet.model_validate(updated_post)

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

        now = self._now()
        await self._repository.soft_delete_post(
            content_id=post_id,
            updated_at=now,
            deleted_at=now,
        )

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
        return [PostGet.model_validate(post) for post in posts]

    async def _set_reaction(
        self,
        *,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> PostRating:
        await self._get_reactable_post(post_id=post_id, viewer_id=user_id)
        await self._repository.set_reaction(
            content_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        return await self._build_rating(post_id=post_id, viewer_id=user_id)

    async def _remove_reaction(
        self,
        *,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> PostRating:
        await self._get_reactable_post(post_id=post_id, viewer_id=user_id)
        await self._repository.remove_reaction(
            content_id=post_id,
            user_id=user_id,
            reaction_type=reaction_type,
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

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
