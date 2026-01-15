"""Tests for rate limiting utilities.

IMPORTANT: Testing time-dependent code requires careful mocking.

The `acquire()` method in RateLimiter has a `while True` loop that:
1. Checks if we're under the rate limit
2. If at limit, calculates wait time and sleeps
3. Loops back to check again

BUG PATTERN TO AVOID:
If you mock `time.time()` to return a CONSTANT value AND mock `time.sleep()`
to no-op, `acquire()` will loop forever because:
- Timestamps never become "old" (time doesn't advance)
- We're always at the limit
- Sleep does nothing
- Loop repeats infinitely, consuming ~0.6MB per 1000 iterations due to mock
  storing call information

CORRECT TESTING PATTERN:
Mock `time.time()` to return ADVANCING values, simulating actual time passage.
This allows the rate limiter's cleanup logic to work correctly.
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from mykrok.services.rate_limiter import (
    MultiRateLimiter,
    RateLimitConfig,
    RateLimiter,
    create_fittrackee_limiter,
    create_strava_limiter,
    rate_limited,
)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.ai_generated
    def test_acquire_when_under_limit(self) -> None:
        """Test acquire succeeds immediately when under limit."""
        config = RateLimitConfig(requests_per_period=5, period_seconds=60.0)
        limiter = RateLimiter(config)

        limiter.acquire()
        assert limiter.current_count == 1

    @pytest.mark.ai_generated
    def test_can_proceed_when_under_limit(self) -> None:
        """Test can_proceed returns True when under limit."""
        config = RateLimitConfig(requests_per_period=3, period_seconds=60.0)
        limiter = RateLimiter(config)

        assert limiter.can_proceed()
        limiter.acquire()
        assert limiter.can_proceed()
        limiter.acquire()
        assert limiter.can_proceed()
        limiter.acquire()
        assert not limiter.can_proceed()

    @pytest.mark.ai_generated
    def test_remaining_count(self) -> None:
        """Test remaining property returns correct count."""
        config = RateLimitConfig(requests_per_period=5, period_seconds=60.0)
        limiter = RateLimiter(config)

        assert limiter.remaining == 5
        limiter.acquire()
        assert limiter.remaining == 4
        limiter.acquire()
        assert limiter.remaining == 3

    @pytest.mark.ai_generated
    def test_time_until_available_when_under_limit(self) -> None:
        """Test time_until_available returns 0 when under limit."""
        config = RateLimitConfig(requests_per_period=5, period_seconds=60.0)
        limiter = RateLimiter(config)

        assert limiter.time_until_available() == 0.0

    @pytest.mark.ai_generated
    def test_time_until_available_when_at_limit(self) -> None:
        """Test time_until_available returns positive when at limit."""
        config = RateLimitConfig(requests_per_period=2, period_seconds=10.0)
        limiter = RateLimiter(config)

        limiter.acquire()
        limiter.acquire()

        wait_time = limiter.time_until_available()
        # Should be close to 10 seconds (period_seconds)
        assert 9.0 < wait_time <= 10.0

    @pytest.mark.ai_generated
    def test_record_request_increases_count(self) -> None:
        """Test record_request tracks requests without waiting."""
        config = RateLimitConfig(requests_per_period=5, period_seconds=60.0)
        limiter = RateLimiter(config)

        limiter.record_request()
        assert limiter.current_count == 1

    @pytest.mark.ai_generated
    def test_acquire_waits_when_at_limit_with_advancing_time(self) -> None:
        """Test acquire waits and succeeds when time advances past period.

        This is the CORRECT way to test acquire() with mocked time:
        Mock time.time() to return advancing values.
        """
        config = RateLimitConfig(requests_per_period=2, period_seconds=1.0)
        limiter = RateLimiter(config)

        # Fill up the limiter
        limiter.acquire()
        limiter.acquire()

        assert limiter.current_count == 2
        assert not limiter.can_proceed()

        # Mock time to advance past the period
        original_time = time.time()

        def advancing_time() -> float:
            return original_time + 2.0  # Jump past the 1-second period

        with (
            patch("mykrok.services.rate_limiter.time.time", side_effect=advancing_time),
            patch("mykrok.services.rate_limiter.time.sleep") as mock_sleep,
        ):
            limiter.acquire()
            # Should succeed without sleeping since time jumped
            mock_sleep.assert_not_called()

        # Old timestamps cleaned up, only new one remains
        assert limiter.current_count == 1

    @pytest.mark.ai_generated
    def test_cleanup_removes_old_timestamps(self) -> None:
        """Test that old timestamps are cleaned up correctly."""
        config = RateLimitConfig(requests_per_period=3, period_seconds=1.0)
        limiter = RateLimiter(config)

        # Add timestamps at a fixed time
        base_time = 1000.0
        with patch("mykrok.services.rate_limiter.time.time", return_value=base_time):
            limiter.acquire()
            limiter.acquire()
            # Check count while still in the mocked time context
            assert limiter.current_count == 2

        # Check count after time has advanced past period
        with patch(
            "mykrok.services.rate_limiter.time.time", return_value=base_time + 2.0
        ):
            # Cleanup happens in current_count via _cleanup_old_timestamps
            assert limiter.current_count == 0  # Old ones cleaned up

    @pytest.mark.ai_generated
    def test_acquire_raises_on_frozen_time(self) -> None:
        """Test that acquire() raises RuntimeError when time appears frozen.

        This protects against buggy test setups where:
        1. time.time() returns a constant (time doesn't advance)
        2. time.sleep() is mocked to no-op

        Without this protection, acquire() would loop forever, consuming
        ~0.6MB per 1000 iterations due to mock storing call arguments.
        """
        config = RateLimitConfig(requests_per_period=2, period_seconds=1.0)
        limiter = RateLimiter(config)

        fixed_time = 1000.0
        with patch("mykrok.services.rate_limiter.time.time", return_value=fixed_time):
            limiter.acquire()
            limiter.acquire()

        # Frozen time + no-op sleep triggers the safeguard
        with (
            patch("mykrok.services.rate_limiter.time.time", return_value=fixed_time),
            patch("mykrok.services.rate_limiter.time.sleep"),
            pytest.raises(RuntimeError, match="Time appears frozen"),
        ):
            limiter.acquire()


class TestMultiRateLimiter:
    """Tests for MultiRateLimiter class."""

    @pytest.mark.ai_generated
    def test_can_proceed_requires_all_limiters(self) -> None:
        """Test can_proceed returns True only if all limiters allow."""
        config1 = RateLimitConfig(requests_per_period=2, period_seconds=60.0)
        config2 = RateLimitConfig(requests_per_period=5, period_seconds=60.0)
        multi = MultiRateLimiter(config1, config2)

        assert multi.can_proceed()

        # Fill first limiter
        multi.acquire()
        multi.acquire()

        # First limiter is full, so can_proceed should be False
        assert not multi.can_proceed()

    @pytest.mark.ai_generated
    def test_time_until_available_returns_max(self) -> None:
        """Test time_until_available returns max across all limiters."""
        config1 = RateLimitConfig(requests_per_period=1, period_seconds=10.0)
        config2 = RateLimitConfig(requests_per_period=1, period_seconds=20.0)
        multi = MultiRateLimiter(config1, config2)

        multi.acquire()

        wait_time = multi.time_until_available()
        # Should be close to 20 seconds (the longer period)
        assert wait_time > 10.0


class TestRateLimitedDecorator:
    """Tests for rate_limited decorator."""

    @pytest.mark.ai_generated
    def test_decorator_calls_limiter_acquire(self) -> None:
        """Test decorator calls acquire before function."""
        config = RateLimitConfig(requests_per_period=10, period_seconds=60.0)
        limiter = RateLimiter(config)

        @rate_limited(limiter)
        def my_func() -> str:
            return "result"

        result = my_func()

        assert result == "result"
        assert limiter.current_count == 1


class TestFactoryFunctions:
    """Tests for limiter factory functions."""

    @pytest.mark.ai_generated
    def test_create_strava_limiter(self) -> None:
        """Test create_strava_limiter returns properly configured limiter."""
        limiter = create_strava_limiter()

        assert isinstance(limiter, MultiRateLimiter)
        # Should have two limiters (15-min and daily)
        assert len(limiter._limiters) == 2

    @pytest.mark.ai_generated
    def test_create_fittrackee_limiter(self) -> None:
        """Test create_fittrackee_limiter returns properly configured limiter."""
        limiter = create_fittrackee_limiter()

        assert isinstance(limiter, RateLimiter)
        assert limiter.config.requests_per_period == 300
        assert limiter.config.period_seconds == 5 * 60
