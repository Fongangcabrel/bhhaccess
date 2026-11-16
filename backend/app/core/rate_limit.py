"""Tiny in-memory failure limiter (per key, sliding window) used on device pairing."""
from collections import defaultdict, deque
from datetime import timedelta

from app.core.clock import Clock
from app.core.exceptions import TooManyAttemptsError


class FailureLimiter:
    def __init__(self, clock: Clock, max_failures: int = 8, window: timedelta = timedelta(minutes=10)) -> None:
        self._clock = clock
        self._max = max_failures
        self._window = window
        self._failures: dict[str, deque] = defaultdict(deque)

    def _prune(self, key: str) -> deque:
        queue = self._failures[key]
        limit = self._clock.now() - self._window
        while queue and queue[0] < limit:
            queue.popleft()
        return queue

    def check(self, key: str) -> None:
        if len(self._prune(key)) >= self._max:
            raise TooManyAttemptsError("Trop de tentatives, réessayez dans quelques minutes")

    def fail(self, key: str) -> None:
        self._prune(key).append(self._clock.now())
