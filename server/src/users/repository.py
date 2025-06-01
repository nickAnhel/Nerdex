import typing as tp
import uuid

from sqlalchemy import delete, desc, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.users.models import SubscriptionModel, UserModel


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        data: dict[str, tp.Any],
    ) -> UserModel:
        stmt = (
            insert(UserModel)
            .values(**data)
            .returning(UserModel)
        )
        res = await self._session.execute(stmt)
        await self._session.commit()
        return res.scalar_one()

    async def get_single(
        self,
        **filters,
    ) -> UserModel:
        query = (
            select(UserModel)
            .filter_by(**filters)
            .options(selectinload(UserModel.subscribed))
            .options(selectinload(UserModel.subscribers))
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def get_multi(
        self,
        order: str,
        order_desc: bool,
        offset: int,
        limit: int,
    ) -> list[UserModel]:
        query = (
            select(UserModel)
            .order_by(desc(order) if order_desc else order)
            .offset(offset)
            .limit(limit)
            .options(selectinload(UserModel.subscribers))
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def search(
        self,
        search_query: str,
        offset: int,
        limit: int,
    ) -> list[UserModel]:
        query = (
            select(UserModel)
            .where(
                or_(
                    UserModel.username.bool_op("%")(search_query),
                    UserModel.username.ilike(f"%{search_query}%"),
                )
            )
            .order_by(
                func.similarity(UserModel.username, search_query).desc(),
            )
            .offset(offset)
            .limit(limit)
            .options(selectinload(UserModel.subscribers))
        )

        res = await self._session.execute(query)
        return list(res.scalars().all())

    async def update(
        self,
        data: dict[str, tp.Any],
        **filters,
    ) -> UserModel:
        stmt = (
            update(UserModel)
            .filter_by(**filters)
            .values(**data)
            .returning(UserModel)
        )

        result = await self._session.execute(stmt)
        await self._session.commit()

        return result.scalar_one()

    async def delete(
        self,
        **filters,
    ) -> bool:
        stmt = (
            delete(UserModel)
            .filter_by(**filters)
        )

        res = await self._session.execute(stmt)
        await self._session.commit()
        return res.rowcount != 0

    async def subscribe(
        self,
        user_id: uuid.UUID,
        subscriber_id: uuid.UUID,
    ) -> None:
        user = await self.get_single(user_id=user_id)
        subscriber = await self.get_single(user_id=subscriber_id)

        if subscriber not in user.subscribers:
            user.subscribers.append(subscriber)
            user.subscribers_count += 1

            await self._session.commit()

    async def unsubscribe(
        self,
        user_id: uuid.UUID,
        subscriber_id: uuid.UUID,
    ) -> None:
        user = await self.get_single(user_id=user_id)
        subscriber = await self.get_single(user_id=subscriber_id)

        user.subscribers.remove(subscriber)
        user.subscribers_count -= 1

        await self._session.commit()

    async def get_subscriptions(
        self,
        user_id: uuid.UUID,
    ) -> list[UserModel]:
        subs_query = (
            select(SubscriptionModel.subscribed_id)
            .filter_by(subscriber_id=user_id)
            .cte()
        )

        query = (
            select(UserModel)
            .join(subs_query, UserModel.user_id == subs_query.c.subscribed_id)
            .options(selectinload(UserModel.subscribers))
        )

        res = await self._session.execute(query)
        return list(res.scalars().all())
