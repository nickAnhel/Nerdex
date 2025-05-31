import typing as tp
import uuid

from sqlalchemy import and_, delete, desc, exists, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.posts.models import DislikesModel, LikesModel, PostModel
from src.users.models import SubscriptionModel


class PostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: dict[str, tp.Any],
    ) -> PostModel:
        stmt = (
            insert(PostModel)
            .values(**data)
            .returning(PostModel)
            .options(selectinload(PostModel.user))
        )

        res = await self._session.execute(stmt)
        await self._session.commit()

        return res.scalar_one()

    async def get_single(
        self,
        **filters,
    ) -> PostModel:
        query = (
            select(PostModel)
            .filter_by(**filters)
            .options(selectinload(PostModel.user))
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_multi(
        self,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[PostModel]:
        query = (
            select(PostModel)
            .order_by(desc(order) if order_desc else order)
            .offset(offset)
            .limit(limit)
            .options(selectinload(PostModel.user))
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_post_rating(
        self,
        **filters,
    ) -> tuple[int, int]:
        query = (
            select(PostModel.likes, PostModel.dislikes)
            .filter_by(**filters)
        )

        res = await self._session.execute(query)
        return res.fetchone().tuple()  # type: ignore

    async def update(
        self,
        data: dict[str, tp.Any],
        **filters,
    ) -> PostModel:
        stmt = (
            update(PostModel)
            .filter_by(**filters)
            .values(**data)
            .returning(PostModel)
            .options(selectinload(PostModel.user))
        )

        result = await self._session.execute(stmt)
        await self._session.commit()

        return result.scalar_one()

    async def delete(
        self,
        **filters,
    ) -> int:
        stmt = (
            delete(PostModel)
            .filter_by(**filters)
        )

        res = await self._session.execute(stmt)
        await self._session.commit()
        return res.rowcount

    async def like(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        insert_like_row_stmt = (
            insert(LikesModel)
            .values(
                post_id=post_id,
                user_id=user_id,
            )
        )

        update_likes_count_stmt = (
            update(PostModel)
            .values(likes=PostModel.likes + 1)
            .filter_by(post_id=post_id)
        )

        update_dislikes_count_stmt = (
            update(PostModel)
            .values(dislikes=PostModel.dislikes - 1)
            .where(
                and_(
                    PostModel.post_id == post_id,
                    exists(
                        select(DislikesModel)
                        .filter_by(
                            post_id=post_id,
                            user_id=user_id,
                        )
                    ),
                )
            )
        )

        delete_dislike_row_stmt = (
            delete(DislikesModel)
            .filter_by(
                post_id=post_id,
                user_id=user_id,
            )
        )

        await self._session.execute(insert_like_row_stmt)
        await self._session.execute(update_likes_count_stmt)
        await self._session.execute(update_dislikes_count_stmt)
        await self._session.execute(delete_dislike_row_stmt)
        await self._session.commit()

    async def unlike(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        update_likes_count_stmt = (
            update(PostModel)
            .values(likes=PostModel.likes - 1)
            .where(
                and_(
                    PostModel.post_id == post_id,
                    exists(
                        select(LikesModel)
                        .filter_by(
                            post_id=post_id,
                            user_id=user_id,
                        )
                    ),
                )
            )
        )

        delete_like_row_stmt = (
            delete(LikesModel)
            .filter_by(
                post_id=post_id,
                user_id=user_id,
            )
        )

        await self._session.execute(update_likes_count_stmt)
        await self._session.execute(delete_like_row_stmt)
        await self._session.commit()

    async def dislike(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        insert_dislike_row_stmt = (
            insert(DislikesModel)
            .values(
                post_id=post_id,
                user_id=user_id,
            )
        )

        update_dislikes_count_stmt = (
            update(PostModel)
            .values(dislikes=PostModel.dislikes + 1)
            .filter_by(post_id=post_id)
        )

        update_likes_count_stmt = (
            update(PostModel)
            .values(likes=PostModel.likes - 1)
            .where(
                and_(
                    PostModel.post_id == post_id,
                    exists(
                        select(LikesModel)
                        .filter_by(
                            post_id=post_id,
                            user_id=user_id,
                        )
                    ),
                )
            )
        )

        delete_like_row_stmt = (
            delete(LikesModel)
            .filter_by(
                post_id=post_id,
                user_id=user_id,
            )
        )

        await self._session.execute(insert_dislike_row_stmt)
        await self._session.execute(update_dislikes_count_stmt)
        await self._session.execute(update_likes_count_stmt)
        await self._session.execute(delete_like_row_stmt)
        await self._session.commit()

    async def undislike(
        self,
        post_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        update_dislikes_count_stmt = (
            update(PostModel)
            .values(dislikes=PostModel.dislikes - 1)
            .where(
                and_(
                    PostModel.post_id == post_id,
                    exists(
                        select(DislikesModel)
                        .filter_by(
                            post_id=post_id,
                            user_id=user_id,
                        )
                    ),
                )
            )
        )

        delete_dislike_row_stmt = (
            delete(DislikesModel)
            .filter_by(
                post_id=post_id,
                user_id=user_id,
            )
        )

        await self._session.execute(update_dislikes_count_stmt)
        await self._session.execute(delete_dislike_row_stmt)
        await self._session.commit()

    async def get_user_subscriptions_posts(
        self,
        user_id: uuid.UUID,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[PostModel]:
        subs_cte = (
            select(SubscriptionModel.subscribed_id)
            .filter_by(subscriber_id=user_id)
            .cte()
        )

        query = (
            select(PostModel)
            .where(PostModel.user_id.in_(subs_cte))
            .order_by(desc(order) if order_desc else order)
            .offset(offset)
            .limit(limit)
            .options(selectinload(PostModel.user))
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def is_liked(
        self,
        user_id: uuid.UUID,
        post_id: uuid.UUID
    ) -> bool:
        query = (
            select(LikesModel)
            .filter_by(
                user_id=user_id,
                post_id=post_id,
            )
        )

        res = await self._session.execute(query)
        return len(res.scalars().all()) == 1

    async def is_disliked(
        self,
        user_id: uuid.UUID,
        post_id: uuid.UUID
    ) -> bool:
        query = (
            select(DislikesModel)
            .filter_by(
                user_id=user_id,
                post_id=post_id,
            )
        )

        res = await self._session.execute(query)
        return len(res.scalars().all()) == 1
