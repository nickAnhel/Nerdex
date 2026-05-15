from __future__ import annotations

import random
from typing import Iterable, Sequence, TypeVar


T = TypeVar("T")


class SeedRandom:
    def __init__(self, seed: int) -> None:
        self._random = random.Random(seed)

    def randint(self, a: int, b: int) -> int:
        return self._random.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        return self._random.uniform(a, b)

    def random(self) -> float:
        return self._random.random()

    def choice(self, values: Sequence[T]) -> T:
        return self._random.choice(values)

    def sample(self, values: Sequence[T], k: int) -> list[T]:
        if k <= 0:
            return []
        k = min(k, len(values))
        return self._random.sample(values, k)

    def shuffled(self, values: Iterable[T]) -> list[T]:
        items = list(values)
        self._random.shuffle(items)
        return items

    def weighted_choice(self, weighted_values: Sequence[tuple[T, float]]) -> T:
        if not weighted_values:
            raise ValueError("weighted_choice requires non-empty sequence")
        total = sum(max(weight, 0.0) for _, weight in weighted_values)
        if total <= 0:
            return weighted_values[0][0]
        ticket = self._random.uniform(0, total)
        cumulative = 0.0
        for value, weight in weighted_values:
            cumulative += max(weight, 0.0)
            if ticket <= cumulative:
                return value
        return weighted_values[-1][0]
