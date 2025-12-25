"""Rate limiting utilities for MyKrok.

Provides rate limiting wrappers for API calls to Strava and FitTrackee.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeVar

    T = TypeVar("T")


@dataclass
class RateLimitConfig:
    """Configuration for a rate limiter.

    Attributes:
        requests_per_period: Maximum requests allowed per period.
        period_seconds: Length of the rate limit period in seconds.
        name: Name for logging purposes.
    """

    requests_per_period: int
    period_seconds: float
    name: str = "default"


# Predefined rate limit configurations
STRAVA_RATE_LIMIT = RateLimitConfig(
    requests_per_period=600,
    period_seconds=15 * 60,  # 15 minutes
    name="strava",
)

STRAVA_DAILY_LIMIT = RateLimitConfig(
    requests_per_period=30000,
    period_seconds=24 * 60 * 60,  # 24 hours
    name="strava_daily",
)

FITTRACKEE_RATE_LIMIT = RateLimitConfig(
    requests_per_period=300,
    period_seconds=5 * 60,  # 5 minutes
    name="fittrackee",
)


class RateLimiter:
    """Thread-safe sliding window rate limiter.

    Tracks request timestamps and blocks/waits when the limit is reached.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize the rate limiter.

        Args:
            config: Rate limit configuration.
        """
        self.config = config
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def _cleanup_old_timestamps(self, now: float) -> None:
        """Remove timestamps older than the rate limit period.

        Args:
            now: Current timestamp.
        """
        cutoff = now - self.config.period_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def can_proceed(self) -> bool:
        """Check if a request can proceed without waiting.

        Returns:
            True if under the rate limit, False otherwise.
        """
        with self._lock:
            now = time.time()
            self._cleanup_old_timestamps(now)
            return len(self._timestamps) < self.config.requests_per_period

    def time_until_available(self) -> float:
        """Get time in seconds until a request slot is available.

        Returns:
            Seconds to wait, or 0.0 if can proceed immediately.
        """
        with self._lock:
            now = time.time()
            self._cleanup_old_timestamps(now)

            if len(self._timestamps) < self.config.requests_per_period:
                return 0.0

            # Need to wait for oldest request to expire
            oldest = self._timestamps[0]
            wait_time = (oldest + self.config.period_seconds) - now
            return max(0.0, wait_time)

    def acquire(self) -> None:
        """Acquire a request slot, waiting if necessary."""
        while True:
            with self._lock:
                now = time.time()
                self._cleanup_old_timestamps(now)

                if len(self._timestamps) < self.config.requests_per_period:
                    self._timestamps.append(now)
                    return

                # Calculate wait time
                oldest = self._timestamps[0]
                wait_time = (oldest + self.config.period_seconds) - now

            if wait_time > 0:
                time.sleep(min(wait_time + 0.1, 1.0))  # Sleep in small increments

    def record_request(self) -> None:
        """Record a request without waiting.

        Use this when you've already made a request and need to track it.
        """
        with self._lock:
            self._timestamps.append(time.time())

    @property
    def current_count(self) -> int:
        """Get the current number of requests in the window.

        Returns:
            Number of requests made in the current period.
        """
        with self._lock:
            self._cleanup_old_timestamps(time.time())
            return len(self._timestamps)

    @property
    def remaining(self) -> int:
        """Get the number of remaining requests in the window.

        Returns:
            Number of requests that can still be made.
        """
        return self.config.requests_per_period - self.current_count


class MultiRateLimiter:
    """Rate limiter that enforces multiple rate limits simultaneously.

    Useful for APIs with both short-term and long-term limits (like Strava).
    """

    def __init__(self, *configs: RateLimitConfig) -> None:
        """Initialize with multiple rate limit configurations.

        Args:
            configs: Rate limit configurations to enforce.
        """
        self._limiters = [RateLimiter(config) for config in configs]

    def can_proceed(self) -> bool:
        """Check if a request can proceed under all rate limits.

        Returns:
            True if all limits allow, False otherwise.
        """
        return all(limiter.can_proceed() for limiter in self._limiters)

    def time_until_available(self) -> float:
        """Get maximum wait time across all limiters.

        Returns:
            Seconds to wait until request can proceed.
        """
        return max(limiter.time_until_available() for limiter in self._limiters)

    def acquire(self) -> None:
        """Acquire a slot from all rate limiters."""
        # Acquire from each limiter
        for limiter in self._limiters:
            limiter.acquire()

    def record_request(self) -> None:
        """Record a request in all limiters."""
        for limiter in self._limiters:
            limiter.record_request()


def rate_limited(
    limiter: RateLimiter | MultiRateLimiter,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to rate-limit a function.

    Args:
        limiter: Rate limiter to use.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args: object, **kwargs: object) -> T:
            limiter.acquire()
            return func(*args, **kwargs)

        return wrapper

    return decorator


def create_strava_limiter() -> MultiRateLimiter:
    """Create a rate limiter configured for Strava API.

    Returns:
        Multi-limiter with both 15-minute and daily limits.
    """
    return MultiRateLimiter(STRAVA_RATE_LIMIT, STRAVA_DAILY_LIMIT)


def create_fittrackee_limiter() -> RateLimiter:
    """Create a rate limiter configured for FitTrackee API.

    Returns:
        Rate limiter with 5-minute limit.
    """
    return RateLimiter(FITTRACKEE_RATE_LIMIT)
