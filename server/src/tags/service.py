from __future__ import annotations

import re
import uuid

from src.tags.exceptions import InvalidTag
from src.tags.models import TagModel
from src.tags.repository import TagRepository
from src.tags.schemas import TagGet

TAG_PATTERN = re.compile(r"^[a-zа-яё]+$")
TAG_VALIDATION_MESSAGE = (
    "Tags must contain only lowercase Latin or Cyrillic letters without spaces, digits, or special characters"
)
DEFAULT_TAG_SUGGESTIONS_LIMIT = 10
MAX_TAG_SUGGESTIONS_LIMIT = 20


class TagService:
    def __init__(self, repository: TagRepository) -> None:
        self._repository = repository

    async def suggest_tags(
        self,
        *,
        prefix: str,
        limit: int = DEFAULT_TAG_SUGGESTIONS_LIMIT,
    ) -> list[TagGet]:
        normalized_prefix = self.normalize_prefix(prefix)
        if not normalized_prefix:
            return []

        tags = await self._repository.suggest_tags(
            prefix=normalized_prefix,
            limit=self._normalize_limit(limit),
        )
        return [TagGet.model_validate(tag) for tag in tags]

    async def resolve_tags(self, slugs: list[str]) -> list[TagModel]:
        normalized_slugs = self.normalize_tags(slugs)
        if not normalized_slugs:
            return []

        return await self._repository.resolve_tags(normalized_slugs)

    async def replace_content_tags(
        self,
        *,
        content_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        commit: bool = True,
    ) -> None:
        await self._repository.replace_content_tags(
            content_id=content_id,
            tag_ids=tag_ids,
            commit=commit,
        )

    def normalize_tags(self, slugs: list[str] | None) -> list[str]:
        if not slugs:
            return []

        normalized_slugs: list[str] = []
        seen: set[str] = set()
        for slug in slugs:
            normalized_slug = self._normalize_single_slug(slug)
            if normalized_slug in seen:
                continue
            seen.add(normalized_slug)
            normalized_slugs.append(normalized_slug)

        return normalized_slugs

    def normalize_prefix(self, prefix: str) -> str:
        normalized_prefix = prefix.strip()
        if not normalized_prefix:
            return ""

        self._validate_slug(normalized_prefix)
        return normalized_prefix

    def _normalize_limit(self, limit: int) -> int:
        if limit < 1:
            return 1
        return min(limit, MAX_TAG_SUGGESTIONS_LIMIT)

    def _normalize_single_slug(self, slug: str) -> str:
        normalized_slug = slug.strip()
        if not normalized_slug:
            raise InvalidTag("Tag cannot be empty")

        self._validate_slug(normalized_slug)
        return normalized_slug

    def _validate_slug(self, slug: str) -> None:
        if len(slug) > 64:
            raise InvalidTag("Tag length must be between 1 and 64 characters")
        if slug != slug.lower():
            raise InvalidTag(TAG_VALIDATION_MESSAGE)
        if not TAG_PATTERN.fullmatch(slug):
            raise InvalidTag(TAG_VALIDATION_MESSAGE)
