from __future__ import annotations

import datetime
import uuid

from src.comments.exceptions import CommentNotFound, InvalidComment
from src.comments.repository import CommentPageResult, CommentRepository
from src.comments.schemas import (
    COMMENT_BODY_MAX_LENGTH,
    CommentCreate,
    CommentGet,
    CommentReactionGet,
    CommentUpdate,
    CommentsPageGet,
    RepliesPageGet,
)
from src.comments.threading import (
    CommentThreadNode,
    MAX_COMMENT_DEPTH,
    build_reply_placement,
    build_root_comment_placement,
)
from src.common.exceptions import PermissionDenied
from src.content.access import can_access_comments, can_view_content
from src.content.enums import ReactionTypeEnum
from src.users.presentation import build_user_get
from src.users.repository import UserRepository
from src.users.schemas import UserGet


class CommentService:
    def __init__(
        self,
        repository: CommentRepository,
        user_repository: UserRepository | None = None,
    ) -> None:
        self._repository = repository
        self._user_repository = user_repository

    async def get_root_comments(
        self,
        *,
        content_id: uuid.UUID,
        offset: int,
        limit: int,
        user: UserGet | None = None,
    ) -> CommentsPageGet:
        viewer_id = user.user_id if user else None
        await self._get_readable_content(content_id=content_id, viewer_id=viewer_id)

        page = await self._repository.list_root_comments(
            content_id=content_id,
            viewer_id=viewer_id,
            offset=offset,
            limit=limit,
        )
        return await self._build_comments_page(page, viewer_id=viewer_id)

    async def create_root_comment(
        self,
        *,
        content_id: uuid.UUID,
        user: UserGet,
        data: CommentCreate,
    ) -> CommentGet:
        await self._get_commentable_content(content_id=content_id, viewer_id=user.user_id)
        body_text = self._normalize_body_text(data.body_text)
        now = self._now()
        placement = build_root_comment_placement()

        comment = await self._repository.create_comment(
            content_id=content_id,
            author_id=user.user_id,
            parent_comment_id=placement.parent_comment_id,
            root_comment_id=placement.root_comment_id,
            reply_to_comment_id=placement.reply_to_comment_id,
            depth=placement.depth,
            body_text=body_text,
            created_at=now,
            updated_at=now,
            commit=False,
        )
        await self._repository.commit()

        return await self._get_comment_view_or_raise(
            comment_id=comment.comment_id,
            viewer_id=user.user_id,
        )

    async def get_replies(
        self,
        *,
        comment_id: uuid.UUID,
        offset: int,
        limit: int,
        user: UserGet | None = None,
    ) -> RepliesPageGet:
        viewer_id = user.user_id if user else None
        parent_comment = await self._get_comment_state_or_raise(comment_id=comment_id)
        await self._get_readable_content(
            content_id=parent_comment.content_id,
            viewer_id=viewer_id,
        )
        if parent_comment.depth == MAX_COMMENT_DEPTH:
            return RepliesPageGet(
                items=[],
                offset=offset,
                limit=limit,
                has_more=False,
            )

        page = await self._repository.list_replies(
            parent_comment_id=comment_id,
            root_comment_id=(
                comment_id
                if parent_comment.depth == 0
                else parent_comment.root_comment_id
            ),
            viewer_id=viewer_id,
            offset=offset,
            limit=limit,
        )
        return RepliesPageGet(
            items=await self._build_comment_get_many(page.items, viewer_id=viewer_id),
            offset=page.offset,
            limit=page.limit,
            has_more=page.has_more,
        )

    async def create_reply(
        self,
        *,
        comment_id: uuid.UUID,
        user: UserGet,
        data: CommentCreate,
    ) -> CommentGet:
        parent_comment = await self._get_comment_state_or_raise(comment_id=comment_id)
        if parent_comment.deleted_at is not None:
            raise CommentNotFound(f"Comment with id {comment_id!s} not found")

        await self._get_commentable_content(
            content_id=parent_comment.content_id,
            viewer_id=user.user_id,
        )
        body_text = self._normalize_body_text(data.body_text)
        now = self._now()
        try:
            placement = build_reply_placement(
                CommentThreadNode(
                    comment_id=parent_comment.comment_id,
                    parent_comment_id=parent_comment.parent_comment_id,
                    root_comment_id=parent_comment.root_comment_id,
                    depth=parent_comment.depth,
                )
            )
        except ValueError as exc:
            raise InvalidComment(str(exc)) from exc

        comment = await self._repository.create_comment(
            content_id=parent_comment.content_id,
            author_id=user.user_id,
            parent_comment_id=placement.parent_comment_id,
            root_comment_id=placement.root_comment_id,
            reply_to_comment_id=placement.reply_to_comment_id,
            depth=placement.depth,
            body_text=body_text,
            created_at=now,
            updated_at=now,
            commit=False,
        )
        await self._repository.commit()

        return await self._get_comment_view_or_raise(
            comment_id=comment.comment_id,
            viewer_id=user.user_id,
        )

    async def update_comment(
        self,
        *,
        comment_id: uuid.UUID,
        user: UserGet,
        data: CommentUpdate,
    ) -> CommentGet:
        comment = await self._get_comment_state_or_raise(comment_id=comment_id)
        await self._get_manageable_content(
            content_id=comment.content_id,
            viewer_id=user.user_id,
        )
        if comment.author_id != user.user_id:
            raise PermissionDenied(
                f"User with id {user.user_id} can't edit comment with id {comment_id}"
            )
        if comment.deleted_at is not None:
            raise InvalidComment("Deleted comment cannot be edited")

        body_text = self._normalize_body_text(data.body_text)
        await self._repository.update_comment_body(
            comment_id=comment_id,
            body_text=body_text,
            updated_at=self._now(),
            commit=False,
        )
        await self._repository.commit()

        return await self._get_comment_view_or_raise(
            comment_id=comment_id,
            viewer_id=user.user_id,
        )

    async def delete_comment(
        self,
        *,
        comment_id: uuid.UUID,
        user: UserGet,
    ) -> None:
        comment = await self._get_comment_state_or_raise(comment_id=comment_id)
        await self._get_manageable_content(
            content_id=comment.content_id,
            viewer_id=user.user_id,
        )
        if comment.author_id != user.user_id:
            raise PermissionDenied(
                f"User with id {user.user_id} can't delete comment with id {comment_id}"
            )
        if comment.deleted_at is not None:
            return

        now = self._now()
        await self._repository.mark_comment_deleted(
            comment_id=comment_id,
            updated_at=now,
            deleted_at=now,
            commit=False,
        )
        await self._repository.clear_comment_reactions(
            comment_id=comment_id,
            commit=False,
        )
        await self._repository.adjust_content_comments_count(
            content_id=comment.content_id,
            delta=-1,
            commit=False,
        )

        if comment.parent_comment_id is not None and comment.replies_count == 0:
            await self._cascade_hidden_deleted_comment(
                parent_comment_id=comment.parent_comment_id,
            )

        await self._repository.commit()

    async def add_like(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CommentReactionGet:
        return await self._set_reaction(
            comment_id=comment_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.LIKE,
        )

    async def remove_like(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CommentReactionGet:
        return await self._remove_reaction(
            comment_id=comment_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.LIKE,
        )

    async def add_dislike(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CommentReactionGet:
        return await self._set_reaction(
            comment_id=comment_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.DISLIKE,
        )

    async def remove_dislike(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CommentReactionGet:
        return await self._remove_reaction(
            comment_id=comment_id,
            user_id=user_id,
            reaction_type=ReactionTypeEnum.DISLIKE,
        )

    async def _set_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> CommentReactionGet:
        await self._get_reactable_comment(comment_id=comment_id, viewer_id=user_id)
        await self._repository.set_reaction(
            comment_id=comment_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        return await self._build_rating(comment_id=comment_id, viewer_id=user_id)

    async def _remove_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> CommentReactionGet:
        await self._get_reactable_comment(comment_id=comment_id, viewer_id=user_id)
        await self._repository.remove_reaction(
            comment_id=comment_id,
            user_id=user_id,
            reaction_type=reaction_type,
        )
        return await self._build_rating(comment_id=comment_id, viewer_id=user_id)

    async def _build_rating(
        self,
        *,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ) -> CommentReactionGet:
        rating = await self._repository.get_comment_rating(
            comment_id=comment_id,
            viewer_id=viewer_id,
        )
        if rating is None:
            raise CommentNotFound(f"Comment with id {comment_id!s} not found")

        return CommentReactionGet.model_validate(rating)

    async def _get_comment_view_or_raise(
        self,
        *,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
    ) -> CommentGet:
        comment = await self._repository.get_comment_view(
            comment_id=comment_id,
            viewer_id=viewer_id,
        )
        if comment is None:
            raise CommentNotFound(f"Comment with id {comment_id!s} not found")

        return await self._build_comment_get(comment, viewer_id=viewer_id)

    async def _get_comment_state_or_raise(
        self,
        *,
        comment_id: uuid.UUID,
    ):
        comment = await self._repository.get_comment_state(comment_id=comment_id)
        if comment is None:
            raise CommentNotFound(f"Comment with id {comment_id!s} not found")
        return comment

    async def _get_commentable_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        content = await self._repository.get_content_state(content_id=content_id)
        if content is None or not can_access_comments(content=content, viewer_id=viewer_id):
            raise CommentNotFound(f"Content with id {content_id!s} not found")
        return content

    async def _get_readable_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
    ):
        content = await self._repository.get_content_state(content_id=content_id)
        if content is None or not can_access_comments(content=content, viewer_id=viewer_id):
            raise CommentNotFound(f"Content with id {content_id!s} not found")
        return content

    async def _get_manageable_content(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        content = await self._repository.get_content_state(content_id=content_id)
        if content is None or not can_view_content(content=content, viewer_id=viewer_id):
            raise CommentNotFound(f"Content with id {content_id!s} not found")
        return content

    async def _get_reactable_comment(
        self,
        *,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID,
    ):
        comment = await self._get_comment_state_or_raise(comment_id=comment_id)
        if comment.deleted_at is not None:
            raise CommentNotFound(f"Comment with id {comment_id!s} not found")

        await self._get_readable_content(
            content_id=comment.content_id,
            viewer_id=viewer_id,
        )
        return comment

    async def _cascade_hidden_deleted_comment(
        self,
        *,
        parent_comment_id: uuid.UUID,
    ) -> None:
        current_parent_id = parent_comment_id

        while current_parent_id is not None:
            parent_comment = await self._get_comment_state_or_raise(comment_id=current_parent_id)
            await self._repository.adjust_comment_replies_count(
                comment_id=current_parent_id,
                delta=-1,
                commit=False,
            )
            if parent_comment.deleted_at is None or parent_comment.replies_count > 1:
                return
            current_parent_id = parent_comment.parent_comment_id

    async def _build_comments_page(
        self,
        page: CommentPageResult,
        *,
        viewer_id: uuid.UUID | None,
    ) -> CommentsPageGet:
        return CommentsPageGet(
            items=await self._build_comment_get_many(page.items, viewer_id=viewer_id),
            offset=page.offset,
            limit=page.limit,
            has_more=page.has_more,
        )

    async def _build_comment_get_many(
        self,
        comments,
        *,
        viewer_id: uuid.UUID | None,
    ) -> list[CommentGet]:
        if self._user_repository is None:
            return [
                await self._build_comment_get(comment, viewer_id=viewer_id)
                for comment in comments
            ]

        author_ids = sorted(
            {
                comment.author.user_id
                for comment in comments
                if comment.author is not None
            }
        )
        authors = await self._user_repository.get_many_by_ids(user_ids=author_ids)
        authors_by_id = {author.user_id: author for author in authors}

        return [
            await self._build_comment_get(comment, viewer_id=viewer_id, authors_by_id=authors_by_id)
            for comment in comments
        ]

    async def _build_comment_get(
        self,
        comment,
        *,
        viewer_id: uuid.UUID | None,
        authors_by_id: dict[uuid.UUID, object] | None = None,
    ) -> CommentGet:
        author = None
        if comment.author is not None:
            full_author = (authors_by_id or {}).get(comment.author.user_id)
            if full_author is not None:
                serialized_author = await build_user_get(full_author, viewer_id=viewer_id)
                author = {
                    "user_id": serialized_author.user_id,
                    "username": serialized_author.username,
                    "avatar": serialized_author.avatar,
                }
            else:
                author = {
                    "user_id": comment.author.user_id,
                    "username": comment.author.username,
                    "avatar": None,
                }

        return CommentGet(
            comment_id=comment.comment_id,
            content_id=comment.content_id,
            author=author,
            parent_comment_id=comment.parent_comment_id,
            root_comment_id=comment.root_comment_id,
            reply_to_comment_id=comment.reply_to_comment_id,
            depth=comment.depth,
            body_text=comment.body_text,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            deleted_at=comment.deleted_at,
            replies_count=comment.replies_count,
            likes_count=comment.likes_count,
            dislikes_count=comment.dislikes_count,
            my_reaction=comment.my_reaction,
            is_owner=comment.is_owner,
            is_deleted=comment.is_deleted,
            reply_to_comment_depth=comment.reply_to_comment_depth,
            reply_to_username=comment.reply_to_username,
            reply_to_comment_ref=comment.reply_to_comment_ref,
        )

    def _normalize_body_text(self, body_text: str) -> str:
        normalized_body_text = body_text.strip()
        if not normalized_body_text:
            raise InvalidComment("Comment body cannot be empty")
        if len(normalized_body_text) > COMMENT_BODY_MAX_LENGTH:
            raise InvalidComment(
                f"Comment body length cannot exceed {COMMENT_BODY_MAX_LENGTH} characters"
            )
        return normalized_body_text

    def _now(self) -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)
