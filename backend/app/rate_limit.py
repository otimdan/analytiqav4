"""Lightweight in-memory rate limiting.

Monthly plan caps stop overall volume; this stops *bursts* — a user firing many
expensive requests in a few seconds (which would spike Fireworks/E2B cost and
hammer the sandbox). Keyed per user, sliding 60s window.

In-memory is fine for a single backend instance. If you scale to multiple
instances later, back this with Redis so the window is shared.
"""
import time
from collections import defaultdict, deque

from app.config import QUERY_RATE_PER_MIN, UPLOAD_RATE_PER_MIN


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float = 60.0):
        self.max = max_events
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        dq = self._hits[key]
        cutoff = now - self.window
        while dq and dq[0] <= cutoff:
            dq.popleft()
        if len(dq) >= self.max:
            return False
        dq.append(now)
        return True


query_limiter = SlidingWindowLimiter(QUERY_RATE_PER_MIN)
upload_limiter = SlidingWindowLimiter(UPLOAD_RATE_PER_MIN)
