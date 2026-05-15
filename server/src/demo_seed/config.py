from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class SeedScale:
    users_total: int = 80
    posts: int = 420
    articles: int = 280
    videos: int = 220
    moments: int = 80
    subscriptions_min: int = 1200
    subscriptions_max: int = 1800
    content_reactions_min: int = 12000
    content_reactions_max: int = 20000
    comments_min: int = 3000
    comments_max: int = 5000
    comment_reactions_min: int = 3000
    comment_reactions_max: int = 8000
    view_sessions_min: int = 30000
    view_sessions_max: int = 60000
    activity_events_min: int = 40000
    activity_events_max: int = 80000
    chats_min: int = 60
    chats_max: int = 90
    messages_min: int = 4000
    messages_max: int = 8000
    message_reactions_min: int = 1000
    message_reactions_max: int = 3000


@dataclass(slots=True, frozen=True)
class SeedPaths:
    package_root: Path
    data_dir: Path
    output_dir: Path
    media_cache_dir: Path
    templates_dir: Path

    @classmethod
    def from_package_root(cls, package_root: Path) -> "SeedPaths":
        return cls(
            package_root=package_root,
            data_dir=package_root / "data",
            output_dir=package_root / "output",
            media_cache_dir=package_root / "media_cache",
            templates_dir=package_root / "data",
        )


@dataclass(slots=True, frozen=True)
class SeedRuntimeConfig:
    seed: int
    reset: bool = False
    dry_run: bool = False
    verbose: bool = False
    collect_only: bool = False


@dataclass(slots=True, frozen=True)
class MediaConfig:
    cache_budget_bytes: int = 10 * 1024 * 1024 * 1024
    review_file_name: str = "media_review.html"


DEFAULT_SCALE = SeedScale()
DEFAULT_MEDIA_CONFIG = MediaConfig()
