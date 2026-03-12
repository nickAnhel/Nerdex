from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, insert, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.comments.models import CommentModel, CommentReactionModel
from src.content.enums import ContentStatusEnum, ContentVisibilityEnum, ReactionTypeEnum
from src.content.models import ContentModel
from src.users.models import UserModel


@dataclass(slots=True)
class ContentState:
    content_id: uuid.UUID
    author_id: uuid.UUID
    status: ContentStatusEnum
    visibility: ContentVisibilityEnum
    deleted_at: datetime.datetime | None


@dataclass(slots=True)
class CommentState:
    comment_id: uuid.UUID
    content_id: uuid.UUID
    author_id: uuid.UUID
    parent_comment_id: uuid.UUID | None
    root_comment_id: uuid.UUID | None
    depth: int
    body_text: str
    replies_count: int
    likes_count: int
    dislikes_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None


@dataclass(slots=True)
class CommentAuthorRow:
    user_id: uuid.UUID
    username: str


@dataclass(slots=True)
class CommentParentRefRow:
    comment_id: uuid.UUID
    is_deleted: bool


@dataclass(slots=True)
class CommentViewRow:
    comment_id: uuid.UUID
    content_id: uuid.UUID
    author: CommentAuthorRow | None
    parent_comment_id: uuid.UUID | None
    root_comment_id: uuid.UUID | None
    depth: int
    body_text: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    deleted_at: datetime.datetime | None
    replies_count: int
    likes_count: int
    dislikes_count: int
    my_reaction: ReactionTypeEnum | None
    is_owner: bool
    is_deleted: bool
    reply_to_username: str | None
    parent_comment_ref: CommentParentRefRow | None


@dataclass(slots=True)
class CommentRatingRow:
    comment_id: uuid.UUID
    likes_count: int
    dislikes_count: int
    my_reaction: ReactionTypeEnum | None


@dataclass(slots=True)
class CommentPageResult:
    items: list[CommentViewRow]
    offset: int
    limit: int
    has_more: bool


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_content_state(
        self,
        *,
        content_id: uuid.UUID,
    ) -> ContentState | None:
        result = await self._session.execute(
            select(
                ContentModel.content_id,
                ContentModel.author_id,
                ContentModel.status,
                ContentModel.visibility,
                ContentModel.deleted_at,
            ).where(ContentModel.content_id == content_id)
        )
        row = result.one_or_none()
        if row is None:
            return None

        return ContentState(
            content_id=row.content_id,
            author_id=row.author_id,
            status=row.status,
            visibility=row.visibility,
            deleted_at=row.deleted_at,
        )

    async def get_comment_state(
        self,
        *,
        comment_id: uuid.UUID,
    ) -> CommentState | None:
        result = await self._session.execute(
            select(
                CommentModel.comment_id,
                CommentModel.content_id,
                CommentModel.author_id,
                CommentModel.parent_comment_id,
                CommentModel.root_comment_id,
                CommentModel.depth,
                CommentModel.body_text,
                CommentModel.replies_count,
                CommentModel.likes_count,
                CommentModel.dislikes_count,
                CommentModel.created_at,
                CommentModel.updated_at,
                CommentModel.deleted_at,
            ).where(CommentModel.comment_id == comment_id)
        )
        row = result.one_or_none()
        if row is None:
            return None

        return CommentState(
            comment_id=row.comment_id,
            content_id=row.content_id,
            author_id=row.author_id,
            parent_comment_id=row.parent_comment_id,
            root_comment_id=row.root_comment_id,
            depth=row.depth,
            body_text=row.body_text,
            replies_count=row.replies_count,
            likes_count=row.likes_count,
            dislikes_count=row.dislikes_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
        )

    async def create_comment(
        self,
        *,
        content_id: uuid.UUID,
        author_id: uuid.UUID,
        parent_comment_id: uuid.UUID | None,
        root_comment_id: uuid.UUID | None,
        depth: int,
        body_text: str,
        created_at: datetime.datetime,
        updated_at: datetime.datetime,
        commit: bool = True,
    ) -> CommentState:
        comment_id = uuid.uuid4()

        await self._session.execute(
            insert(CommentModel).values(
                comment_id=comment_id,
                content_id=content_id,
                author_id=author_id,
                parent_comment_id=parent_comment_id,
                root_comment_id=root_comment_id,
                depth=depth,
                body_text=body_text,
                created_at=created_at,
                updated_at=updated_at,
            )
        )
        await self.adjust_content_comments_count(
            content_id=content_id,
            delta=1,
            commit=False,
        )
        if parent_comment_id is not None:
            await self.adjust_comment_replies_count(
                comment_id=parent_comment_id,
                delta=1,
                commit=False,
            )

        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

        comment = await self.get_comment_state(comment_id=comment_id)
        if comment is None:
            raise RuntimeError("Created comment could not be loaded")

        return comment

    async def update_comment_body(
        self,
        *,
        comment_id: uuid.UUID,
        body_text: str,
        updated_at: datetime.datetime,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(CommentModel)
            .where(CommentModel.comment_id == comment_id)
            .values(
                body_text=body_text,
                updated_at=updated_at,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def mark_comment_deleted(
        self,
        *,
        comment_id: uuid.UUID,
        updated_at: datetime.datetime,
        deleted_at: datetime.datetime,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(CommentModel)
            .where(CommentModel.comment_id == comment_id)
            .values(
                updated_at=updated_at,
                deleted_at=deleted_at,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def clear_comment_reactions(
        self,
        *,
        comment_id: uuid.UUID,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            delete(CommentReactionModel).where(CommentReactionModel.comment_id == comment_id)
        )
        await self._session.execute(
            update(CommentModel)
            .where(CommentModel.comment_id == comment_id)
            .values(
                likes_count=0,
                dislikes_count=0,
            )
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def adjust_content_comments_count(
        self,
        *,
        content_id: uuid.UUID,
        delta: int,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(ContentModel)
            .where(ContentModel.content_id == content_id)
            .values(comments_count=ContentModel.comments_count + delta)
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def adjust_comment_replies_count(
        self,
        *,
        comment_id: uuid.UUID,
        delta: int,
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            update(CommentModel)
            .where(CommentModel.comment_id == comment_id)
            .values(replies_count=CommentModel.replies_count + delta)
        )
        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def get_comment_view(
        self,
        *,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
    ) -> CommentViewRow | None:
        stmt = self._build_comment_view_statement(viewer_id=viewer_id).where(
            CommentModel.comment_id == comment_id
        )
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None

        return self._map_comment_view_row(row=row, viewer_id=viewer_id)

    async def list_root_comments(
        self,
        *,
        content_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> CommentPageResult:
        return await self._list_comments(
            viewer_id=viewer_id,
            offset=offset,
            limit=limit,
            order_by=CommentModel.created_at.desc(),
            where_clause=(
                CommentModel.content_id == content_id,
                CommentModel.parent_comment_id.is_(None),
            ),
        )

    async def list_replies(
        self,
        *,
        parent_comment_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
    ) -> CommentPageResult:
        return await self._list_comments(
            viewer_id=viewer_id,
            offset=offset,
            limit=limit,
            order_by=CommentModel.created_at.asc(),
            where_clause=(CommentModel.parent_comment_id == parent_comment_id,),
        )

    async def get_comment_rating(
        self,
        *,
        comment_id: uuid.UUID,
        viewer_id: uuid.UUID | None,
    ) -> CommentRatingRow | None:
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)
        my_reaction_column = (
            reaction_subquery.c.reaction_type if reaction_subquery is not None else literal(None)
        )

        stmt = select(
            CommentModel.comment_id,
            CommentModel.likes_count,
            CommentModel.dislikes_count,
            my_reaction_column.label("my_reaction"),
        ).where(CommentModel.comment_id == comment_id)

        if reaction_subquery is not None:
            stmt = stmt.outerjoin(
                reaction_subquery,
                CommentModel.comment_id == reaction_subquery.c.comment_id,
            )

        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None

        return CommentRatingRow(
            comment_id=row.comment_id,
            likes_count=row.likes_count,
            dislikes_count=row.dislikes_count,
            my_reaction=row.my_reaction,
        )

    async def set_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        existing = await self._get_reaction(comment_id=comment_id, user_id=user_id)

        if existing is None:
            await self._session.execute(
                insert(CommentReactionModel).values(
                    comment_id=comment_id,
                    user_id=user_id,
                    reaction_type=reaction_type,
                )
            )
            await self._update_reaction_counters(
                comment_id=comment_id,
                like_delta=1 if reaction_type == ReactionTypeEnum.LIKE else 0,
                dislike_delta=1 if reaction_type == ReactionTypeEnum.DISLIKE else 0,
            )
            await self._session.commit()
            return

        if existing.reaction_type == reaction_type:
            return

        await self._session.execute(
            update(CommentReactionModel)
            .where(CommentReactionModel.comment_id == comment_id)
            .where(CommentReactionModel.user_id == user_id)
            .values(reaction_type=reaction_type)
        )
        await self._update_reaction_counters(
            comment_id=comment_id,
            like_delta=1 if reaction_type == ReactionTypeEnum.LIKE else -1,
            dislike_delta=1 if reaction_type == ReactionTypeEnum.DISLIKE else -1,
        )
        await self._session.commit()

    async def remove_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
        reaction_type: ReactionTypeEnum,
    ) -> None:
        existing = await self._get_reaction(comment_id=comment_id, user_id=user_id)
        if existing is None or existing.reaction_type != reaction_type:
            return

        await self._session.execute(
            delete(CommentReactionModel)
            .where(CommentReactionModel.comment_id == comment_id)
            .where(CommentReactionModel.user_id == user_id)
        )
        await self._update_reaction_counters(
            comment_id=comment_id,
            like_delta=-1 if reaction_type == ReactionTypeEnum.LIKE else 0,
            dislike_delta=-1 if reaction_type == ReactionTypeEnum.DISLIKE else 0,
        )
        await self._session.commit()

    async def commit(self) -> None:
        await self._session.commit()

    async def _list_comments(
        self,
        *,
        viewer_id: uuid.UUID | None,
        offset: int,
        limit: int,
        order_by,
        where_clause: tuple,
    ) -> CommentPageResult:
        stmt = (
            self._build_comment_view_statement(viewer_id=viewer_id)
            .where(*where_clause)
            .where(self._visible_comment_clause())
            .order_by(order_by)
            .offset(offset)
            .limit(limit + 1)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        items = [
            self._map_comment_view_row(row=row, viewer_id=viewer_id)
            for row in rows[:limit]
        ]
        return CommentPageResult(
            items=items,
            offset=offset,
            limit=limit,
            has_more=len(rows) > limit,
        )

    def _build_comment_view_statement(
        self,
        *,
        viewer_id: uuid.UUID | None,
    ):
        comment_author = aliased(UserModel)
        parent_comment = aliased(CommentModel)
        parent_author = aliased(UserModel)
        reaction_subquery = self._reaction_subquery(viewer_id=viewer_id)
        my_reaction_column = (
            reaction_subquery.c.reaction_type if reaction_subquery is not None else literal(None)
        )

        stmt = (
            select(
                CommentModel.comment_id,
                CommentModel.content_id,
                CommentModel.parent_comment_id,
                CommentModel.root_comment_id,
                CommentModel.depth,
                CommentModel.body_text,
                CommentModel.created_at,
                CommentModel.updated_at,
                CommentModel.deleted_at,
                CommentModel.replies_count,
                CommentModel.likes_count,
                CommentModel.dislikes_count,
                CommentModel.author_id.label("author_id"),
                comment_author.username.label("author_username"),
                my_reaction_column.label("my_reaction"),
                parent_comment.comment_id.label("parent_ref_comment_id"),
                parent_comment.deleted_at.label("parent_deleted_at"),
                parent_author.username.label("reply_to_username"),
            )
            .select_from(CommentModel)
            .outerjoin(comment_author, comment_author.user_id == CommentModel.author_id)
            .outerjoin(parent_comment, parent_comment.comment_id == CommentModel.parent_comment_id)
            .outerjoin(parent_author, parent_author.user_id == parent_comment.author_id)
        )
        if reaction_subquery is not None:
            stmt = stmt.outerjoin(
                reaction_subquery,
                CommentModel.comment_id == reaction_subquery.c.comment_id,
            )

        return stmt

    def _map_comment_view_row(
        self,
        *,
        row,
        viewer_id: uuid.UUID | None,
    ) -> CommentViewRow:
        is_deleted = row.deleted_at is not None
        author = None
        if not is_deleted and row.author_id is not None and row.author_username is not None:
            author = CommentAuthorRow(
                user_id=row.author_id,
                username=row.author_username,
            )

        parent_comment_ref = None
        if row.parent_ref_comment_id is not None:
            parent_comment_ref = CommentParentRefRow(
                comment_id=row.parent_ref_comment_id,
                is_deleted=row.parent_deleted_at is not None,
            )

        reply_to_username = None
        if row.parent_ref_comment_id is not None and row.parent_deleted_at is None:
            reply_to_username = row.reply_to_username

        return CommentViewRow(
            comment_id=row.comment_id,
            content_id=row.content_id,
            author=author,
            parent_comment_id=row.parent_comment_id,
            root_comment_id=row.root_comment_id,
            depth=row.depth,
            body_text=None if is_deleted else row.body_text,
            created_at=row.created_at,
            updated_at=row.updated_at,
            deleted_at=row.deleted_at,
            replies_count=row.replies_count,
            likes_count=row.likes_count,
            dislikes_count=row.dislikes_count,
            my_reaction=row.my_reaction,
            is_owner=viewer_id is not None and row.author_id == viewer_id,
            is_deleted=is_deleted,
            reply_to_username=reply_to_username,
            parent_comment_ref=parent_comment_ref,
        )

    def _visible_comment_clause(self):
        return or_(
            CommentModel.deleted_at.is_(None),
            CommentModel.replies_count > 0,
        )

    def _reaction_subquery(
        self,
        *,
        viewer_id: uuid.UUID | None,
    ):
        if viewer_id is None:
            return None

        return (
            select(
                CommentReactionModel.comment_id,
                CommentReactionModel.reaction_type,
            )
            .where(CommentReactionModel.user_id == viewer_id)
            .subquery()
        )

    async def _get_reaction(
        self,
        *,
        comment_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CommentReactionModel | None:
        result = await self._session.execute(
            select(CommentReactionModel)
            .where(CommentReactionModel.comment_id == comment_id)
            .where(CommentReactionModel.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def _update_reaction_counters(
        self,
        *,
        comment_id: uuid.UUID,
        like_delta: int,
        dislike_delta: int,
    ) -> None:
        await self._session.execute(
            update(CommentModel)
            .where(CommentModel.comment_id == comment_id)
            .values(
                likes_count=CommentModel.likes_count + like_delta,
                dislikes_count=CommentModel.dislikes_count + dislike_delta,
            )
        )
