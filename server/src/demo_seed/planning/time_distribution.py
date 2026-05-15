from __future__ import annotations

import datetime as dt

from src.demo_seed.planning.random_state import SeedRandom


class TimeDistributor:
    def __init__(self, random: SeedRandom, now: dt.datetime | None = None) -> None:
        self._random = random
        self._now = now or dt.datetime.now(dt.timezone.utc)

    @property
    def now(self) -> dt.datetime:
        return self._now

    def random_user_created_at(self) -> dt.datetime:
        return self._sample_weighted_age()

    def random_content_created_at(self) -> dt.datetime:
        return self._sample_weighted_age()

    def random_after(self, base: dt.datetime, min_minutes: int = 5, max_days: int = 120) -> dt.datetime:
        minutes = self._random.randint(min_minutes, max_days * 24 * 60)
        return min(self._now, base + dt.timedelta(minutes=minutes))

    def random_between(self, start: dt.datetime, end: dt.datetime) -> dt.datetime:
        if end <= start:
            return start
        seconds = int((end - start).total_seconds())
        return start + dt.timedelta(seconds=self._random.randint(0, max(seconds, 1)))

    def _sample_weighted_age(self) -> dt.datetime:
        # 15%: 9-12 months, 25%: 3-9 months, 35%: 1-3 months, 25%: last 30 days
        bucket = self._random.weighted_choice([
            ((270, 365), 0.15),
            ((90, 270), 0.25),
            ((30, 90), 0.35),
            ((0, 30), 0.25),
        ])
        min_days, max_days = bucket
        days = self._random.randint(min_days, max_days)
        seconds = self._random.randint(0, 86399)
        return self._now - dt.timedelta(days=days, seconds=seconds)
