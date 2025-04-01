import typing as tp

from sqlalchemy import insert, select, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.posts.models import PostModel


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
        )

        result = await self._session.execute(query)
        return list(result.scalars().all())

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
