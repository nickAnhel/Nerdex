import uuid
from dataclasses import dataclass

import pytest

from src.tags.exceptions import InvalidTag
from src.tags.service import TagService


@dataclass
class FakeTag:
    tag_id: uuid.UUID
    slug: str


class FakeTagRepository:
    def __init__(self) -> None:
        self.tags_by_slug: dict[str, FakeTag] = {}

    async def suggest_tags(
        self,
        *,
        prefix: str,
        limit: int,
    ) -> list[FakeTag]:
        matching_tags = [
            tag for slug, tag in sorted(self.tags_by_slug.items())
            if slug.startswith(prefix)
        ]
        return matching_tags[:limit]

    async def resolve_tags(self, slugs: list[str]) -> list[FakeTag]:
        resolved_tags: list[FakeTag] = []
        for slug in slugs:
            tag = self.tags_by_slug.get(slug)
            if tag is None:
                tag = FakeTag(tag_id=uuid.uuid4(), slug=slug)
                self.tags_by_slug[slug] = tag
            resolved_tags.append(tag)
        return resolved_tags

    async def replace_content_tags(
        self,
        *,
        content_id: uuid.UUID,
        tag_ids: list[uuid.UUID],
        commit: bool = True,
    ) -> None:
        return None

    def seed_tag(self, slug: str) -> None:
        self.tags_by_slug[slug] = FakeTag(tag_id=uuid.uuid4(), slug=slug)


@pytest.fixture
def tag_service() -> TagService:
    repository = FakeTagRepository()
    return TagService(repository=repository)  # type: ignore[arg-type]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_invalid_empty_tag_is_rejected(tag_service: TagService) -> None:
    with pytest.raises(InvalidTag):
        tag_service.normalize_tags([""])


def test_uppercase_tag_is_rejected(tag_service: TagService) -> None:
    with pytest.raises(InvalidTag):
        tag_service.normalize_tags(["Python"])


def test_tag_with_space_is_rejected(tag_service: TagService) -> None:
    with pytest.raises(InvalidTag):
        tag_service.normalize_tags(["py thon"])


def test_tag_with_special_character_is_rejected(tag_service: TagService) -> None:
    with pytest.raises(InvalidTag):
        tag_service.normalize_tags(["python!"])


def test_tag_with_digit_is_rejected(tag_service: TagService) -> None:
    with pytest.raises(InvalidTag):
        tag_service.normalize_tags(["python3"])


def test_cyrillic_tag_is_accepted(tag_service: TagService) -> None:
    assert tag_service.normalize_tags(["тест"]) == ["тест"]


def test_latin_tag_is_accepted(tag_service: TagService) -> None:
    assert tag_service.normalize_tags(["python"]) == ["python"]


def test_mixed_latin_and_cyrillic_tag_is_accepted(tag_service: TagService) -> None:
    assert tag_service.normalize_tags(["pythonтест"]) == ["pythonтест"]


@pytest.mark.anyio
async def test_suggestions_return_only_matching_tags(tag_service: TagService) -> None:
    repository = tag_service._repository  # type: ignore[attr-defined]
    repository.seed_tag("python")
    repository.seed_tag("pytest")
    repository.seed_tag("backend")

    suggestions = await tag_service.suggest_tags(prefix="py", limit=10)

    assert [tag.slug for tag in suggestions] == ["pytest", "python"]


@pytest.mark.anyio
async def test_suggestions_can_return_unused_matching_tags(tag_service: TagService) -> None:
    repository = tag_service._repository  # type: ignore[attr-defined]
    repository.seed_tag("django")

    suggestions = await tag_service.suggest_tags(prefix="d", limit=10)

    assert [tag.slug for tag in suggestions] == ["django"]


@pytest.mark.anyio
async def test_suggestions_filter_out_non_matching_tags(tag_service: TagService) -> None:
    repository = tag_service._repository  # type: ignore[attr-defined]
    repository.seed_tag("python")
    repository.seed_tag("backend")

    suggestions = await tag_service.suggest_tags(prefix="py", limit=10)

    assert [tag.slug for tag in suggestions] == ["python"]


@pytest.mark.anyio
async def test_suggestions_are_sorted_by_slug(tag_service: TagService) -> None:
    repository = tag_service._repository  # type: ignore[attr-defined]
    repository.seed_tag("python")
    repository.seed_tag("pytest")
    repository.seed_tag("pyramid")

    suggestions = await tag_service.suggest_tags(prefix="py", limit=10)

    assert [tag.slug for tag in suggestions] == ["pyramid", "pytest", "python"]


@pytest.mark.anyio
async def test_suggestions_respect_limit(tag_service: TagService) -> None:
    repository = tag_service._repository  # type: ignore[attr-defined]
    repository.seed_tag("panda")
    repository.seed_tag("parrot")
    repository.seed_tag("patch")

    suggestions = await tag_service.suggest_tags(prefix="pa", limit=2)

    assert len(suggestions) == 2
