from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass(slots=True)
class CachedMediaItem:
    media_id: str
    provider: str
    provider_item_id: str
    media_type: str
    topic: str
    role: str
    query: str
    local_path: str
    width: int | None
    height: int | None
    duration_seconds: int | None
    orientation: str | None
    size_bytes: int
    source_url: str
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class CacheIndex:
    items: list[CachedMediaItem] = field(default_factory=list)

    def add(self, item: CachedMediaItem) -> None:
        self.items.append(item)

    def by_role(self, role: str) -> list[CachedMediaItem]:
        return [item for item in self.items if item.role == role]

    def by_topic(self, topic: str) -> list[CachedMediaItem]:
        return [item for item in self.items if item.topic == topic]

    @property
    def total_size_bytes(self) -> int:
        return sum(item.size_bytes for item in self.items)


def load_cache_index(path: Path) -> CacheIndex:
    if not path.exists():
        return CacheIndex()
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    items = [CachedMediaItem(**item) for item in payload.get("items", [])]
    return CacheIndex(items=items)


def save_cache_index(path: Path, cache_index: CacheIndex) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump({"items": [asdict(item) for item in cache_index.items]}, file, ensure_ascii=False, indent=2)
