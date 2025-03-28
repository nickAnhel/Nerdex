import typing as tp

from sqlalchemy import insert, select, update, delete, desc, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import UserModel


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
