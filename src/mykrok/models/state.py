"""Sync state tracking for MyKrok.

Tracks last sync timestamps, export states, and retry queues for failed activities.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from mykrok.lib.paths import (
    ensure_exports_dir,
    get_athlete_dir,
    get_fittrackee_export_path,
)


class FailureType(Enum):
    """Categorized failure types for retry scheduling."""

    RATE_LIMIT = "rate_limit"  # 429 errors - back off significantly
    TIMEOUT = "timeout"  # Request timeouts - retry soon
    SERVER_ERROR = "server_error"  # 5xx errors - retry with backoff
    NOT_FOUND = "not_found"  # 404 errors - don't retry
    AUTH_ERROR = "auth_error"  # 401/403 - don't retry, needs re-auth
    UNKNOWN = "unknown"  # Other errors

    @classmethod
    def from_error(cls, error: Exception) -> FailureType:
        """Categorize an exception into a failure type.

        Args:
            error: The exception that occurred.

        Returns:
            Appropriate FailureType.
        """
        error_str = str(error).lower()

        if "429" in error_str or "rate limit" in error_str:
            return cls.RATE_LIMIT
        if "timeout" in error_str or "timed out" in error_str:
            return cls.TIMEOUT
        if "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
            return cls.SERVER_ERROR
        if "404" in error_str or "not found" in error_str:
            return cls.NOT_FOUND
        if "401" in error_str or "403" in error_str or "unauthorized" in error_str:
            return cls.AUTH_ERROR

        return cls.UNKNOWN


# Backoff configuration per failure type (base delay in seconds)
BACKOFF_CONFIG: dict[FailureType, dict[str, int | float]] = {
    FailureType.RATE_LIMIT: {"base_delay": 900, "max_delay": 3600, "max_retries": 10},  # 15min base
    FailureType.TIMEOUT: {"base_delay": 60, "max_delay": 1800, "max_retries": 5},  # 1min base
    FailureType.SERVER_ERROR: {"base_delay": 300, "max_delay": 3600, "max_retries": 5},  # 5min base
    FailureType.NOT_FOUND: {"base_delay": 0, "max_delay": 0, "max_retries": 0},  # Don't retry
    FailureType.AUTH_ERROR: {"base_delay": 0, "max_delay": 0, "max_retries": 0},  # Don't retry
    FailureType.UNKNOWN: {"base_delay": 300, "max_delay": 3600, "max_retries": 3},  # 5min base
}


@dataclass
class FailedActivity:
    """Record of a failed activity sync attempt."""

    activity_id: int
    failure_type: FailureType
    error_message: str
    failed_at: datetime
    retry_count: int = 0
    next_retry_after: datetime | None = None

    def __post_init__(self) -> None:
        """Calculate next retry time if not set."""
        if self.next_retry_after is None:
            self.next_retry_after = self._calculate_next_retry()

    def _calculate_next_retry(self) -> datetime | None:
        """Calculate next retry time using exponential backoff.

        Returns:
            Next retry datetime or None if max retries exceeded.
        """
        config = BACKOFF_CONFIG.get(self.failure_type, BACKOFF_CONFIG[FailureType.UNKNOWN])
        max_retries = int(config["max_retries"])

        if max_retries == 0 or self.retry_count >= max_retries:
            return None

        base_delay = config["base_delay"]
        max_delay = config["max_delay"]

        # Exponential backoff: base_delay * 2^retry_count
        delay_seconds = min(base_delay * (2**self.retry_count), max_delay)

        return self.failed_at + timedelta(seconds=delay_seconds)

    def is_due_for_retry(self, now: datetime | None = None) -> bool:
        """Check if this activity is due for retry.

        Args:
            now: Current time (defaults to now).

        Returns:
            True if retry should be attempted.
        """
        if self.next_retry_after is None:
            return False

        if now is None:
            now = datetime.now()

        return now >= self.next_retry_after

    def is_permanently_failed(self) -> bool:
        """Check if this activity has permanently failed (no more retries).

        Returns:
            True if no more retries will be attempted.
        """
        return self.next_retry_after is None

    def record_retry_failure(self, error: Exception) -> None:
        """Record another failed retry attempt.

        Args:
            error: The exception that occurred.
        """
        self.retry_count += 1
        self.failure_type = FailureType.from_error(error)
        self.error_message = str(error)
        self.failed_at = datetime.now()
        self.next_retry_after = self._calculate_next_retry()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "activity_id": self.activity_id,
            "failure_type": self.failure_type.value,
            "error_message": self.error_message,
            "failed_at": self.failed_at.isoformat(),
            "retry_count": self.retry_count,
            "next_retry_after": self.next_retry_after.isoformat()
            if self.next_retry_after
            else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailedActivity:
        """Create from dictionary.

        Args:
            data: Dictionary with entry data.

        Returns:
            FailedActivity instance.
        """
        failed_at = data["failed_at"]
        if isinstance(failed_at, str):
            failed_at = datetime.fromisoformat(failed_at)

        next_retry_after = data.get("next_retry_after")
        if isinstance(next_retry_after, str):
            next_retry_after = datetime.fromisoformat(next_retry_after)

        return cls(
            activity_id=data["activity_id"],
            failure_type=FailureType(data["failure_type"]),
            error_message=data["error_message"],
            failed_at=failed_at,
            retry_count=data.get("retry_count", 0),
            next_retry_after=next_retry_after,
        )


@dataclass
class RetryQueue:
    """Queue of failed activities awaiting retry."""

    failed_activities: list[FailedActivity] = field(default_factory=list)

    def add_failure(self, activity_id: int, error: Exception) -> FailedActivity:
        """Add a failed activity to the queue.

        If the activity is already in the queue, updates the existing entry.

        Args:
            activity_id: Strava activity ID.
            error: The exception that occurred.

        Returns:
            The FailedActivity entry.
        """
        # Check if already in queue
        existing = self.get_failure(activity_id)
        if existing:
            existing.record_retry_failure(error)
            return existing

        # Create new entry
        failure_type = FailureType.from_error(error)
        entry = FailedActivity(
            activity_id=activity_id,
            failure_type=failure_type,
            error_message=str(error),
            failed_at=datetime.now(),
        )

        # Only add if retryable
        if not entry.is_permanently_failed():
            self.failed_activities.append(entry)

        return entry

    def get_failure(self, activity_id: int) -> FailedActivity | None:
        """Get failure entry for an activity.

        Args:
            activity_id: Strava activity ID.

        Returns:
            FailedActivity or None if not in queue.
        """
        for entry in self.failed_activities:
            if entry.activity_id == activity_id:
                return entry
        return None

    def remove(self, activity_id: int) -> bool:
        """Remove an activity from the retry queue (e.g., after success).

        Args:
            activity_id: Strava activity ID.

        Returns:
            True if removed, False if not found.
        """
        original_len = len(self.failed_activities)
        self.failed_activities = [f for f in self.failed_activities if f.activity_id != activity_id]
        return len(self.failed_activities) < original_len

    def get_due_retries(self, now: datetime | None = None) -> list[FailedActivity]:
        """Get activities that are due for retry.

        Args:
            now: Current time (defaults to now).

        Returns:
            List of FailedActivity entries due for retry.
        """
        if now is None:
            now = datetime.now()

        return [f for f in self.failed_activities if f.is_due_for_retry(now)]

    def get_pending_count(self) -> int:
        """Get count of activities pending retry.

        Returns:
            Number of activities in the queue.
        """
        return len(self.failed_activities)

    def get_permanently_failed(self) -> list[FailedActivity]:
        """Get activities that have permanently failed.

        Returns:
            List of permanently failed activities.
        """
        return [f for f in self.failed_activities if f.is_permanently_failed()]

    def cleanup_permanent_failures(self) -> int:
        """Remove permanently failed activities from the queue.

        Returns:
            Number of entries removed.
        """
        original_len = len(self.failed_activities)
        self.failed_activities = [
            f for f in self.failed_activities if not f.is_permanently_failed()
        ]
        return original_len - len(self.failed_activities)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "failed_activities": [f.to_dict() for f in self.failed_activities],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RetryQueue:
        """Create from dictionary.

        Args:
            data: Dictionary with queue data.

        Returns:
            RetryQueue instance.
        """
        queue = cls()
        for entry_data in data.get("failed_activities", []):
            queue.failed_activities.append(FailedActivity.from_dict(entry_data))
        return queue


@dataclass
class SyncState:
    """Tracks sync state for an athlete."""

    last_sync: datetime | None = None
    last_activity_date: datetime | None = None
    total_activities: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_activity_date": self.last_activity_date.isoformat()
            if self.last_activity_date
            else None,
            "total_activities": self.total_activities,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncState:
        """Create from dictionary.

        Args:
            data: Dictionary with state data.

        Returns:
            SyncState instance.
        """
        last_sync = data.get("last_sync")
        if isinstance(last_sync, str):
            last_sync = datetime.fromisoformat(last_sync)

        last_activity_date = data.get("last_activity_date")
        if isinstance(last_activity_date, str):
            last_activity_date = datetime.fromisoformat(last_activity_date)

        return cls(
            last_sync=last_sync,
            last_activity_date=last_activity_date,
            total_activities=data.get("total_activities", 0),
        )


@dataclass
class FitTrackeeExportEntry:
    """Record of an activity exported to FitTrackee."""

    ses: str  # Session key (datetime format)
    ft_workout_id: int
    exported_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "ses": self.ses,
            "ft_workout_id": self.ft_workout_id,
            "exported_at": self.exported_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitTrackeeExportEntry:
        """Create from dictionary.

        Args:
            data: Dictionary with entry data.

        Returns:
            FitTrackeeExportEntry instance.
        """
        exported_at = data["exported_at"]
        if isinstance(exported_at, str):
            exported_at = datetime.fromisoformat(exported_at.replace("Z", "+00:00"))

        return cls(
            ses=data["ses"],
            ft_workout_id=data["ft_workout_id"],
            exported_at=exported_at,
        )


@dataclass
class FitTrackeeExportState:
    """Tracks which activities have been exported to FitTrackee."""

    fittrackee_url: str = ""
    exports: list[FitTrackeeExportEntry] = field(default_factory=list)

    def is_exported(self, session_key: str) -> bool:
        """Check if a session has been exported.

        Args:
            session_key: Session key to check.

        Returns:
            True if already exported.
        """
        return any(e.ses == session_key for e in self.exports)

    def get_export(self, session_key: str) -> FitTrackeeExportEntry | None:
        """Get export entry for a session.

        Args:
            session_key: Session key.

        Returns:
            Export entry or None.
        """
        for entry in self.exports:
            if entry.ses == session_key:
                return entry
        return None

    def record_export(
        self,
        session_key: str,
        ft_workout_id: int,
        exported_at: datetime | None = None,
    ) -> None:
        """Record an export.

        Args:
            session_key: Session key.
            ft_workout_id: FitTrackee workout ID.
            exported_at: Export timestamp (defaults to now).
        """
        if exported_at is None:
            exported_at = datetime.now()

        # Remove existing entry if present
        self.exports = [e for e in self.exports if e.ses != session_key]

        self.exports.append(
            FitTrackeeExportEntry(
                ses=session_key,
                ft_workout_id=ft_workout_id,
                exported_at=exported_at,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "fittrackee_url": self.fittrackee_url,
            "exports": [e.to_dict() for e in self.exports],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FitTrackeeExportState:
        """Create from dictionary.

        Args:
            data: Dictionary with state data.

        Returns:
            FitTrackeeExportState instance.
        """
        state = cls(fittrackee_url=data.get("fittrackee_url", ""))
        for entry_data in data.get("exports", []):
            state.exports.append(FitTrackeeExportEntry.from_dict(entry_data))
        return state


def get_sync_state_path(athlete_dir: Path) -> Path:
    """Get path to sync state file.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to sync_state.json.
    """
    return athlete_dir / "sync_state.json"


def load_sync_state(data_dir: Path, username: str) -> SyncState:
    """Load sync state for an athlete.

    Args:
        data_dir: Base data directory.
        username: Athlete username.

    Returns:
        SyncState instance.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    state_path = get_sync_state_path(athlete_dir)

    if not state_path.exists():
        return SyncState()

    with open(state_path, encoding="utf-8") as f:
        data = json.load(f)

    return SyncState.from_dict(data)


def save_sync_state(data_dir: Path, username: str, state: SyncState) -> Path:
    """Save sync state for an athlete.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        state: Sync state to save.

    Returns:
        Path to saved file.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    athlete_dir.mkdir(parents=True, exist_ok=True)

    state_path = get_sync_state_path(athlete_dir)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)

    return state_path


def load_fittrackee_export_state(data_dir: Path, username: str) -> FitTrackeeExportState:
    """Load FitTrackee export state.

    Args:
        data_dir: Base data directory.
        username: Athlete username.

    Returns:
        FitTrackeeExportState instance.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    export_path = get_fittrackee_export_path(athlete_dir)

    if not export_path.exists():
        return FitTrackeeExportState()

    with open(export_path, encoding="utf-8") as f:
        data = json.load(f)

    return FitTrackeeExportState.from_dict(data)


def save_fittrackee_export_state(
    data_dir: Path,
    username: str,
    state: FitTrackeeExportState,
) -> Path:
    """Save FitTrackee export state.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        state: Export state to save.

    Returns:
        Path to saved file.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    ensure_exports_dir(athlete_dir)

    export_path = get_fittrackee_export_path(athlete_dir)
    with open(export_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)

    return export_path


def get_retry_queue_path(athlete_dir: Path) -> Path:
    """Get path to retry queue file.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to retry_queue.json.
    """
    return athlete_dir / "retry_queue.json"


def load_retry_queue(data_dir: Path, username: str) -> RetryQueue:
    """Load retry queue for an athlete.

    Args:
        data_dir: Base data directory.
        username: Athlete username.

    Returns:
        RetryQueue instance.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    queue_path = get_retry_queue_path(athlete_dir)

    if not queue_path.exists():
        return RetryQueue()

    with open(queue_path, encoding="utf-8") as f:
        data = json.load(f)

    return RetryQueue.from_dict(data)


def save_retry_queue(data_dir: Path, username: str, queue: RetryQueue) -> Path:
    """Save retry queue for an athlete.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        queue: Retry queue to save.

    Returns:
        Path to saved file.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    athlete_dir.mkdir(parents=True, exist_ok=True)

    queue_path = get_retry_queue_path(athlete_dir)

    # Only write if there are entries, otherwise delete the file
    if queue.get_pending_count() == 0:
        if queue_path.exists():
            queue_path.unlink()
        return queue_path

    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue.to_dict(), f, indent=2)

    return queue_path
