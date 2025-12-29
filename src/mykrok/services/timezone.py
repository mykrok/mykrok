"""Timezone history tracking and correction for activities.

This module provides functionality to:
1. Detect timezone from GPS coordinates
2. Track timezone changes over time per athlete
3. Apply correct local times to activities (overriding potentially wrong Strava data)

The timezone history is stored per athlete and survives re-syncs from Strava.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if TYPE_CHECKING:
    from collections.abc import Iterator

log = logging.getLogger(__name__)

# Minimum time between timezone changes to avoid flickering at borders
DEFAULT_MIN_CHANGE_INTERVAL = timedelta(hours=4)

# Maximum reasonable timezone jump (more than this suggests data error)
MAX_REASONABLE_OFFSET_CHANGE = timedelta(hours=14)


@dataclass
class TimezoneChange:
    """A recorded timezone change."""

    datetime_utc: datetime
    timezone: str
    source: str  # e.g., "gps:ses=20240615T190000", "config:initial", "manual"

    def to_row(self) -> dict[str, str]:
        """Convert to TSV row."""
        return {
            "datetime_utc": self.datetime_utc.strftime("%Y-%m-%dT%H:%M:%S"),
            "timezone": self.timezone,
            "source": self.source,
        }

    @classmethod
    def from_row(cls, row: dict[str, str]) -> TimezoneChange:
        """Create from TSV row."""
        dt_str = row["datetime_utc"]
        # Handle both with and without timezone info
        if "+" in dt_str or dt_str.endswith("Z"):
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            dt = dt.replace(tzinfo=None)  # Store as naive UTC
        else:
            dt = datetime.fromisoformat(dt_str)
        return cls(
            datetime_utc=dt,
            timezone=row["timezone"],
            source=row["source"],
        )


class TimezoneHistory:
    """Manages timezone history for an athlete.

    The history is a list of timezone changes sorted by datetime.
    To find the timezone at any point in time, we find the most recent
    change before that time.
    """

    TSV_COLUMNS = ["datetime_utc", "timezone", "source"]

    def __init__(self, athlete_dir: Path, default_timezone: str = "UTC"):
        """Initialize timezone history.

        Args:
            athlete_dir: Path to athlete directory (e.g., data/athl=username)
            default_timezone: Timezone to use before any recorded changes
        """
        self.athlete_dir = athlete_dir
        self.history_path = athlete_dir / "timezone-history.tsv"
        self.default_timezone = default_timezone
        self._changes: list[TimezoneChange] = []
        self._load()

    def _load(self) -> None:
        """Load history from file."""
        self._changes = []
        if not self.history_path.exists():
            return

        with open(self.history_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                try:
                    change = TimezoneChange.from_row(row)
                    self._changes.append(change)
                except (KeyError, ValueError) as e:
                    log.warning(f"Skipping invalid timezone history row: {row} ({e})")

        # Ensure sorted
        self._changes.sort(key=lambda c: c.datetime_utc)

    def save(self) -> None:
        """Save history to file."""
        self._changes.sort(key=lambda c: c.datetime_utc)

        with open(self.history_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=self.TSV_COLUMNS, delimiter="\t", extrasaction="ignore"
            )
            writer.writeheader()
            for change in self._changes:
                writer.writerow(change.to_row())

    def get_timezone_at(self, dt_utc: datetime) -> str:
        """Get the timezone that was active at a given UTC datetime.

        Args:
            dt_utc: UTC datetime (naive or aware)

        Returns:
            IANA timezone name (e.g., 'America/New_York')
        """
        # Normalize to naive for comparison
        if dt_utc.tzinfo is not None:
            dt_utc = dt_utc.replace(tzinfo=None)

        # Find the most recent change before this time
        active_tz = self.default_timezone
        for change in self._changes:
            if change.datetime_utc <= dt_utc:
                active_tz = change.timezone
            else:
                break

        return active_tz

    def get_local_time(self, dt_utc: datetime) -> datetime:
        """Convert UTC datetime to correct local time.

        Args:
            dt_utc: UTC datetime

        Returns:
            Local datetime with timezone info
        """
        # Ensure we have a UTC-aware datetime
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))

        tz_name = self.get_timezone_at(dt_utc)
        try:
            tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            log.warning(f"Unknown timezone {tz_name}, using UTC")
            tz = ZoneInfo("UTC")

        return dt_utc.astimezone(tz)

    def add_change(
        self,
        dt_utc: datetime,
        timezone: str,
        source: str,
        min_interval: timedelta | None = None,
    ) -> tuple[bool, str]:
        """Add a timezone change, with sanity checks.

        Args:
            dt_utc: UTC datetime of the change
            timezone: IANA timezone name
            source: Source of the change (e.g., "gps:ses=20240615T190000")
            min_interval: Minimum time since last change (default: 4 hours)

        Returns:
            Tuple of (success, message)
        """
        if min_interval is None:
            min_interval = DEFAULT_MIN_CHANGE_INTERVAL

        # Normalize datetime
        if dt_utc.tzinfo is not None:
            dt_utc = dt_utc.replace(tzinfo=None)

        # Validate timezone name
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            return False, f"Invalid timezone name: {timezone}"

        # Check if this is actually a change
        current_tz = self.get_timezone_at(dt_utc)
        if current_tz == timezone:
            return False, f"Already in timezone {timezone} at this time"

        # Check for rapid changes
        recent_changes = [
            c
            for c in self._changes
            if abs((c.datetime_utc - dt_utc).total_seconds()) < min_interval.total_seconds()
        ]
        if recent_changes:
            return (
                False,
                f"Too close to existing timezone change at {recent_changes[0].datetime_utc} "
                f"(within {min_interval}). Use force=True to override.",
            )

        # Check for impossible jumps (validate offset change)
        validation_result = self._validate_offset_change(dt_utc, timezone)
        if not validation_result[0]:
            return validation_result

        # Add the change
        change = TimezoneChange(datetime_utc=dt_utc, timezone=timezone, source=source)
        self._changes.append(change)
        self._changes.sort(key=lambda c: c.datetime_utc)

        return True, f"Added timezone change to {timezone} at {dt_utc}"

    def add_change_force(
        self,
        dt_utc: datetime,
        timezone: str,
        source: str,
    ) -> tuple[bool, str]:
        """Add a timezone change, bypassing sanity checks.

        Use with caution - this skips the rapid change and offset validation.
        """
        if dt_utc.tzinfo is not None:
            dt_utc = dt_utc.replace(tzinfo=None)

        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            return False, f"Invalid timezone name: {timezone}"

        # Remove any existing change at the exact same time
        self._changes = [c for c in self._changes if c.datetime_utc != dt_utc]

        change = TimezoneChange(datetime_utc=dt_utc, timezone=timezone, source=source)
        self._changes.append(change)
        self._changes.sort(key=lambda c: c.datetime_utc)

        return True, f"Force-added timezone change to {timezone} at {dt_utc}"

    def _validate_offset_change(
        self, dt_utc: datetime, new_timezone: str
    ) -> tuple[bool, str]:
        """Validate that the offset change is reasonable.

        Returns:
            Tuple of (valid, message)
        """
        current_tz_name = self.get_timezone_at(dt_utc)

        try:
            current_tz = ZoneInfo(current_tz_name)
            new_tz = ZoneInfo(new_timezone)
        except ZoneInfoNotFoundError:
            return True, "OK"  # Can't validate, allow it

        # Get offsets at this time
        dt_aware = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
        current_offset = dt_aware.astimezone(current_tz).utcoffset()
        new_offset = dt_aware.astimezone(new_tz).utcoffset()

        if current_offset is None or new_offset is None:
            return True, "OK"

        offset_change = abs(new_offset - current_offset)
        if offset_change > MAX_REASONABLE_OFFSET_CHANGE:
            return (
                False,
                f"Offset change of {offset_change} exceeds maximum of "
                f"{MAX_REASONABLE_OFFSET_CHANGE}. This may indicate a data error. "
                f"Use force=True to override.",
            )

        return True, "OK"

    def get_changes(self) -> list[TimezoneChange]:
        """Get all timezone changes."""
        return list(self._changes)

    def clear(self) -> None:
        """Clear all timezone changes."""
        self._changes = []

    def __len__(self) -> int:
        return len(self._changes)

    def __iter__(self) -> Iterator[TimezoneChange]:
        return iter(self._changes)


def detect_timezone_from_coords(
    lat: float, lng: float
) -> str | None:
    """Detect timezone from GPS coordinates.

    Args:
        lat: Latitude
        lng: Longitude

    Returns:
        IANA timezone name or None if detection failed
    """
    # Validate coordinates
    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        log.warning(f"Invalid coordinates: lat={lat}, lng={lng}")
        return None

    # Check for Null Island (common GPS error)
    if abs(lat) < 0.1 and abs(lng) < 0.1:
        log.warning(f"Coordinates near Null Island (0,0), likely GPS error: {lat}, {lng}")
        return None

    try:
        from timezonefinder import TimezoneFinder

        tf = TimezoneFinder()
        tz: str | None = tf.timezone_at(lat=lat, lng=lng)
        if tz is None:
            log.warning(f"Could not determine timezone for {lat}, {lng} (ocean/invalid)")
        return tz
    except ImportError:
        log.warning(
            "timezonefinder not installed. Install with: pip install timezonefinder"
        )
        return None
    except Exception as e:
        log.warning(f"Error detecting timezone for {lat}, {lng}: {e}")
        return None


def get_timezone_history_path(athlete_dir: Path) -> Path:
    """Get path to timezone history file."""
    return athlete_dir / "timezone-history.tsv"


def validate_timezone_history(history: TimezoneHistory) -> list[str]:
    """Validate a timezone history for potential issues.

    Returns:
        List of warning messages (empty if no issues)
    """
    warnings: list[str] = []
    changes = history.get_changes()

    if not changes:
        return warnings

    # Check for rapid changes
    for i in range(1, len(changes)):
        prev = changes[i - 1]
        curr = changes[i]
        interval = curr.datetime_utc - prev.datetime_utc

        if interval < DEFAULT_MIN_CHANGE_INTERVAL:
            warnings.append(
                f"Rapid timezone change: {prev.timezone} -> {curr.timezone} "
                f"in {interval} (at {curr.datetime_utc})"
            )

    # Check for back-and-forth within short period
    if len(changes) >= 3:
        for i in range(2, len(changes)):
            if changes[i].timezone == changes[i - 2].timezone:
                span = changes[i].datetime_utc - changes[i - 2].datetime_utc
                if span < timedelta(hours=24):
                    warnings.append(
                        f"Timezone flickering: {changes[i-2].timezone} -> "
                        f"{changes[i-1].timezone} -> {changes[i].timezone} "
                        f"within {span}"
                    )

    # Check for valid timezone names
    for change in changes:
        try:
            ZoneInfo(change.timezone)
        except ZoneInfoNotFoundError:
            warnings.append(f"Invalid timezone name: {change.timezone}")

    return warnings
