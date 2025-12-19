"""Sync state tracking for strava-backup.

Tracks last sync timestamps and export states.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from strava_backup.lib.paths import (
    ensure_exports_dir,
    get_athlete_dir,
    get_fittrackee_export_path,
)


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
            "last_activity_date": self.last_activity_date.isoformat() if self.last_activity_date else None,
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

        self.exports.append(FitTrackeeExportEntry(
            ses=session_key,
            ft_workout_id=ft_workout_id,
            exported_at=exported_at,
        ))

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

    with open(state_path) as f:
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
    with open(state_path, "w") as f:
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

    with open(export_path) as f:
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
    with open(export_path, "w") as f:
        json.dump(state.to_dict(), f, indent=2)

    return export_path
