from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from src.common.database import async_session_maker
from src.config import settings
from src.demo_seed.config import DEFAULT_MEDIA_CONFIG, DEFAULT_SCALE, SeedPaths, SeedScale
from src.demo_seed.planning.random_state import SeedRandom


@dataclass(slots=True)
class SeedRunContext:
    seed: int
    seed_run_id: str
    started_at: dt.datetime
    paths: SeedPaths
    random: SeedRandom
    scale: SeedScale = field(default_factory=lambda: DEFAULT_SCALE)
    media_config: object = field(default_factory=lambda: DEFAULT_MEDIA_CONFIG)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)

    @classmethod
    def create(cls, seed: int) -> "SeedRunContext":
        started_at = dt.datetime.now(dt.timezone.utc)
        seed_run_id = f"seed-{started_at.strftime('%Y%m%d%H%M%S')}-{seed}"
        package_root = Path(__file__).resolve().parent
        paths = SeedPaths.from_package_root(package_root)
        paths.output_dir.mkdir(parents=True, exist_ok=True)
        paths.media_cache_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            seed=seed,
            seed_run_id=seed_run_id,
            started_at=started_at,
            paths=paths,
            random=SeedRandom(seed),
        )


def get_session_maker():
    return async_session_maker


def get_storage_settings():
    return settings.storage
