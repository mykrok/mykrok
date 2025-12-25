"""Unit tests for retry queue functionality."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mykrok.models.state import (
    BACKOFF_CONFIG,
    FailedActivity,
    FailureType,
    RetryQueue,
)


@pytest.mark.ai_generated
class TestFailureType:
    """Tests for FailureType categorization."""

    def test_rate_limit_detection(self) -> None:
        """Test that rate limit errors are correctly categorized."""
        error = Exception("429 Client Error: Too Many Requests [Rate Limit Exceeded]")
        assert FailureType.from_error(error) == FailureType.RATE_LIMIT

    def test_timeout_detection(self) -> None:
        """Test that timeout errors are correctly categorized."""
        error = Exception("Connection timed out")
        assert FailureType.from_error(error) == FailureType.TIMEOUT

    def test_server_error_detection(self) -> None:
        """Test that server errors are correctly categorized."""
        for code in ["500", "502", "503", "504"]:
            error = Exception(f"{code} Internal Server Error")
            assert FailureType.from_error(error) == FailureType.SERVER_ERROR

    def test_not_found_detection(self) -> None:
        """Test that 404 errors are correctly categorized."""
        error = Exception("404 Not Found")
        assert FailureType.from_error(error) == FailureType.NOT_FOUND

    def test_auth_error_detection(self) -> None:
        """Test that auth errors are correctly categorized."""
        error = Exception("401 Unauthorized")
        assert FailureType.from_error(error) == FailureType.AUTH_ERROR

    def test_unknown_error_detection(self) -> None:
        """Test that unknown errors are correctly categorized."""
        error = Exception("Something went wrong")
        assert FailureType.from_error(error) == FailureType.UNKNOWN


@pytest.mark.ai_generated
class TestFailedActivity:
    """Tests for FailedActivity dataclass."""

    def test_creation_with_rate_limit(self) -> None:
        """Test creating a failed activity with rate limit error."""
        entry = FailedActivity(
            activity_id=12345,
            failure_type=FailureType.RATE_LIMIT,
            error_message="Rate limit exceeded",
            failed_at=datetime.now(),
        )

        assert entry.activity_id == 12345
        assert entry.failure_type == FailureType.RATE_LIMIT
        assert entry.retry_count == 0
        assert entry.next_retry_after is not None
        assert not entry.is_permanently_failed()

    def test_exponential_backoff(self) -> None:
        """Test that backoff increases exponentially."""
        base_time = datetime.now()
        entry = FailedActivity(
            activity_id=12345,
            failure_type=FailureType.RATE_LIMIT,
            error_message="Rate limit",
            failed_at=base_time,
        )

        # First retry should be after base_delay
        config = BACKOFF_CONFIG[FailureType.RATE_LIMIT]
        expected_delay = config["base_delay"]
        assert entry.next_retry_after is not None
        actual_delay = (entry.next_retry_after - base_time).total_seconds()
        assert actual_delay == expected_delay

        # Simulate retry failure - delay should double
        entry.record_retry_failure(Exception("Rate limit"))
        assert entry.retry_count == 1
        expected_delay_2 = min(config["base_delay"] * 2, config["max_delay"])
        assert entry.next_retry_after is not None
        actual_delay_2 = (entry.next_retry_after - entry.failed_at).total_seconds()
        assert actual_delay_2 == expected_delay_2

    def test_permanent_failure_for_not_found(self) -> None:
        """Test that NOT_FOUND errors don't get retried."""
        entry = FailedActivity(
            activity_id=12345,
            failure_type=FailureType.NOT_FOUND,
            error_message="Activity not found",
            failed_at=datetime.now(),
        )

        assert entry.is_permanently_failed()
        assert entry.next_retry_after is None

    def test_max_retries_reached(self) -> None:
        """Test that max retries causes permanent failure."""
        entry = FailedActivity(
            activity_id=12345,
            failure_type=FailureType.UNKNOWN,
            error_message="Unknown error",
            failed_at=datetime.now(),
        )

        config = BACKOFF_CONFIG[FailureType.UNKNOWN]
        max_retries = int(config["max_retries"])

        # Simulate max retries
        for _ in range(max_retries):
            entry.record_retry_failure(Exception("Unknown error"))

        assert entry.is_permanently_failed()
        assert entry.retry_count == max_retries

    def test_is_due_for_retry(self) -> None:
        """Test is_due_for_retry logic."""
        past_time = datetime.now() - timedelta(hours=1)
        entry = FailedActivity(
            activity_id=12345,
            failure_type=FailureType.TIMEOUT,
            error_message="Timeout",
            failed_at=past_time,
        )

        # With TIMEOUT base delay of 60 seconds, should be due after 1 hour
        assert entry.is_due_for_retry()

    def test_to_dict_and_from_dict(self) -> None:
        """Test serialization round-trip."""
        original = FailedActivity(
            activity_id=12345,
            failure_type=FailureType.RATE_LIMIT,
            error_message="Rate limit exceeded",
            failed_at=datetime.now(),
            retry_count=2,
        )

        data = original.to_dict()
        restored = FailedActivity.from_dict(data)

        assert restored.activity_id == original.activity_id
        assert restored.failure_type == original.failure_type
        assert restored.error_message == original.error_message
        assert restored.retry_count == original.retry_count


@pytest.mark.ai_generated
class TestRetryQueue:
    """Tests for RetryQueue."""

    def test_add_failure(self) -> None:
        """Test adding a failure to the queue."""
        queue = RetryQueue()
        error = Exception("429 Rate limit")

        entry = queue.add_failure(12345, error)

        assert queue.get_pending_count() == 1
        assert entry.activity_id == 12345
        assert entry.failure_type == FailureType.RATE_LIMIT

    def test_add_failure_updates_existing(self) -> None:
        """Test that adding same activity updates existing entry."""
        queue = RetryQueue()
        error1 = Exception("Rate limit")
        error2 = Exception("Timeout")

        queue.add_failure(12345, error1)
        queue.add_failure(12345, error2)

        assert queue.get_pending_count() == 1
        entry = queue.get_failure(12345)
        assert entry is not None
        assert entry.retry_count == 1

    def test_remove(self) -> None:
        """Test removing an activity from the queue."""
        queue = RetryQueue()
        queue.add_failure(12345, Exception("Error"))
        queue.add_failure(67890, Exception("Error"))

        assert queue.get_pending_count() == 2

        removed = queue.remove(12345)
        assert removed
        assert queue.get_pending_count() == 1
        assert queue.get_failure(12345) is None

    def test_remove_nonexistent(self) -> None:
        """Test removing a non-existent activity."""
        queue = RetryQueue()
        removed = queue.remove(12345)
        assert not removed

    def test_get_due_retries(self) -> None:
        """Test getting activities due for retry."""
        queue = RetryQueue()
        past_time = datetime.now() - timedelta(hours=2)

        # Add an activity that failed in the past (should be due)
        entry = FailedActivity(
            activity_id=12345,
            failure_type=FailureType.TIMEOUT,
            error_message="Timeout",
            failed_at=past_time,
        )
        queue.failed_activities.append(entry)

        # Add an activity that just failed (not due yet)
        queue.add_failure(67890, Exception("Rate limit"))

        due = queue.get_due_retries()
        assert len(due) == 1
        assert due[0].activity_id == 12345

    def test_cleanup_permanent_failures(self) -> None:
        """Test cleaning up permanent failures."""
        queue = RetryQueue()

        # Add a retryable failure
        queue.add_failure(12345, Exception("Timeout"))

        # Add a permanent failure (NOT_FOUND)
        entry = FailedActivity(
            activity_id=67890,
            failure_type=FailureType.NOT_FOUND,
            error_message="Not found",
            failed_at=datetime.now(),
        )
        queue.failed_activities.append(entry)

        assert queue.get_pending_count() == 2

        removed = queue.cleanup_permanent_failures()
        assert removed == 1
        assert queue.get_pending_count() == 1
        assert queue.get_failure(12345) is not None
        assert queue.get_failure(67890) is None

    def test_to_dict_and_from_dict(self) -> None:
        """Test serialization round-trip."""
        queue = RetryQueue()
        queue.add_failure(12345, Exception("Rate limit"))
        queue.add_failure(67890, Exception("Timeout"))

        data = queue.to_dict()
        restored = RetryQueue.from_dict(data)

        assert restored.get_pending_count() == queue.get_pending_count()
        assert restored.get_failure(12345) is not None
        assert restored.get_failure(67890) is not None

    def test_non_retryable_not_added(self) -> None:
        """Test that non-retryable failures are not added to queue."""
        queue = RetryQueue()
        error = Exception("404 Not Found")

        entry = queue.add_failure(12345, error)

        # Entry is returned but marked as permanent
        assert entry.is_permanently_failed()
        # Queue should not contain it
        assert queue.get_pending_count() == 0
