"""Per-(user, agent) token-bucket rate limiting.

In-process only — state lives in a module-level dict, not a shared store.
Correct scope for a single-process deployment; a multi-instance deployment
would need a Redis-backed bucket instead, which is out of scope here. This
limitation is deliberate, not an oversight: don't pretend it's distributed.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """Token bucket: `capacity` tokens max, refilling at `refill_per_sec`."""

    def __init__(self, capacity: int, refill_per_sec: float):
        self.capacity = capacity
        self.refill_per_sec = refill_per_sec
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill_ts)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, float]:
        """Try to consume one token for `key`. Returns (allowed, retry_after_s)."""
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.refill_per_sec)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return True, 0.0
            self._buckets[key] = (tokens, now)
            deficit = 1.0 - tokens
            retry_after = deficit / self.refill_per_sec if self.refill_per_sec > 0 else float("inf")
            return False, retry_after


_limiters: dict[str, RateLimiter] = {}
_limiters_lock = threading.Lock()


def _get_limiter(agent_name: str, *, capacity: int, refill_per_min: int) -> RateLimiter:
    with _limiters_lock:
        limiter = _limiters.get(agent_name)
        if limiter is None:
            limiter = RateLimiter(capacity=capacity, refill_per_sec=refill_per_min / 60.0)
            _limiters[agent_name] = limiter
        return limiter


def check_rate_limit(
    agent_name: str, user_id: str, *, capacity: int = 10, refill_per_min: int = 30
) -> tuple[bool, float]:
    """Return (allowed, retry_after_s) for this (user, agent) pair.

    One limiter instance per agent, keyed internally by user_id, so agents
    with different `rate_limit_per_min`/`rate_limit_burst` config don't share
    a bucket. `capacity`/`refill_per_min` are only used the first time an
    agent's limiter is created — later calls reuse the same instance.
    """
    limiter = _get_limiter(agent_name, capacity=capacity, refill_per_min=refill_per_min)
    return limiter.allow(user_id or "anonymous")


def reset_all() -> None:
    """Test-only: clear all limiter state between tests."""
    with _limiters_lock:
        _limiters.clear()
