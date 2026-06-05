"""A tiny in-process sliding-window rate limiter for the public sample run.

For a single API instance this is sufficient and dependency-free. A multi-
instance deployment would back this with Redis or a Postgres counter — called
out in the README as a known tradeoff.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, per_seconds: float) -> None:
        self.max_events = max_events
        self.window = per_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            dq = self._hits[key]
            cutoff = now - self.window
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= self.max_events:
                retry_after = int(self.window - (now - dq[0])) + 1
                return False, max(retry_after, 1)
            dq.append(now)
            return True, 0
