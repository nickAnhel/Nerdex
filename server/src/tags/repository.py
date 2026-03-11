from __future__ import annotations

import uuid

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.tags.models import ContentTagModel, TagModel


class TagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def suggest_tags(
        self,
        *,
        prefix: str,
        limit: int,
    ) -> list[TagModel]:
        stmt = (
            select(TagModel)
            .where(TagModel.slug.startswith(prefix))
            .order_by(TagModel.slug.asc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def resolve_tags(self, slugs: list[str]) -> list[TagModel]:
        if not slugs:
            return []

        existing = await self._get_by_slugs(slugs)
        existing_by_slug = {tag.slug: tag for tag in existing}
        missing_slugs = [slug for slug in slugs if slug not in existing_by_slug]

        if missing_slugs:
            await self._session.execute(
                pg_insert(TagModel)
                .values([{"slug": slug} for slug in missing_slugs])
                .on_conflict_do_nothing(index_elements=[TagModel.slug])
            )
            await self._session.flush()
            existing = await self._get_by_slugs(slugs)
            existing_by_slug = {tag.slug: tag for tag in existing}

        return [existing_by_slug[slug] for slug in slugs]

    async def replace_content_tags(
        self,
        *,
        content_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        commit: bool = True,
    ) -> None:
        await self._session.execute(
            delete(ContentTagModel).where(ContentTagModel.content_id == content_id)
        )

        if tag_ids:
            unique_tag_ids = list(dict.fromkeys(tag_ids))
            await self._session.execute(
                insert(ContentTagModel).values(
                    [
                        {
                            "content_id": content_id,
                            "tag_id": tag_id,
                        }
                        for tag_id in unique_tag_ids
                    ]
                )
            )

        if commit:
            await self._session.commit()
        else:
            await self._session.flush()

    async def commit(self) -> None:
        await self._session.commit()

    async def _get_by_slugs(self, slugs: list[str]) -> list[TagModel]:
        result = await self._session.execute(
            select(TagModel).where(TagModel.slug.in_(slugs))
        )
        by_slug = {tag.slug: tag for tag in result.scalars().all()}
        return [by_slug[slug] for slug in slugs if slug in by_slug]
