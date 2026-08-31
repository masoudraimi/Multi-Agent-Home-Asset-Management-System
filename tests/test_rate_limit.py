"""Tests for core.rate_limit's token-bucket limiter."""

from __future__ import annotations

import pytest

from core.rate_limit import RateLimiter, check_rate_limit, reset_all


@pytest.fixture(autouse=True)
def _reset():
    reset_all()
    yield
    reset_all()


def test_allows_up_to_capacity_then_blocks():
    limiter = RateLimiter(capacity=3, refill_per_sec=0.0)
    for _ in range(3):
        allowed, _ = limiter.allow("user-1")
        assert allowed is True
    allowed, retry_after = limiter.allow("user-1")
    assert allowed is False
    assert retry_after == float("inf")  # refill_per_sec=0 means it never recovers


def test_refill_over_time(monkeypatch: pytest.MonkeyPatch):
    limiter = RateLimiter(capacity=1, refill_per_sec=10.0)  # 1 token per 0.1s
    fake_now = [1000.0]
    monkeypatch.setattr("time.monotonic", lambda: fake_now[0])

    allowed, _ = limiter.allow("user-1")
    assert allowed is True
    allowed, retry_after = limiter.allow("user-1")
    assert allowed is False
    assert retry_after == pytest.approx(0.1, rel=0.01)

    fake_now[0] += 0.1
    allowed, _ = limiter.allow("user-1")
    assert allowed is True


def test_buckets_are_isolated_per_key():
    limiter = RateLimiter(capacity=1, refill_per_sec=0.0)
    assert limiter.allow("user-a")[0] is True
    assert limiter.allow("user-a")[0] is False
    assert limiter.allow("user-b")[0] is True  # separate bucket, unaffected


def test_check_rate_limit_reuses_limiter_per_agent():
    for _ in range(5):
        allowed, _ = check_rate_limit("asset", "user-1", capacity=5, refill_per_min=0)
        assert allowed is True
    allowed, retry_after = check_rate_limit("asset", "user-1", capacity=5, refill_per_min=0)
    assert allowed is False


def test_check_rate_limit_scopes_by_agent_not_just_user():
    for _ in range(3):
        assert check_rate_limit("asset", "user-1", capacity=3, refill_per_min=0)[0] is True
    assert check_rate_limit("asset", "user-1", capacity=3, refill_per_min=0)[0] is False
    # Different agent -> different limiter instance, fresh bucket.
    assert check_rate_limit("maintenance", "user-1", capacity=3, refill_per_min=0)[0] is True
