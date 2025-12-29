"""Activity model and storage operations.

Handles activity metadata storage, retrieval, and sessions.tsv summary generation.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from mykrok.lib.paths import (
    get_athlete_dir,
    get_info_path,
    get_session_dir,
    get_sessions_tsv_path,
    iter_session_dirs,
)
from mykrok.models.tracking import get_coordinates, load_tracking_manifest


def _duration_to_seconds(duration: Any) -> int:
    """Convert a duration value to seconds.

    Handles stravalib Duration objects, timedelta, and numeric values.

    Args:
        duration: Duration value (stravalib Duration, timedelta, or number).

    Returns:
        Duration in seconds as integer.
    """
    if duration is None:
        return 0

    # Python timedelta
    if isinstance(duration, timedelta):
        return int(duration.total_seconds())

    # stravalib Duration - check for seconds attribute
    if hasattr(duration, "seconds"):
        return int(duration.seconds)

    # Already a number
    if isinstance(duration, int | float):
        return int(duration)

    # Try to convert to int (stravalib Duration may be int-like)
    try:
        return int(duration)
    except (TypeError, ValueError):
        return 0


def _extract_enum_value(enum_value: Any) -> str:
    """Extract string value from stravalib enum/pydantic model.

    stravalib uses pydantic models for enums that stringify as "root='Value'"
    instead of just "Value". This extracts the actual value.

    Args:
        enum_value: An enum-like value from stravalib (e.g., ActivityType).

    Returns:
        The string value (e.g., "Workout" instead of "root='Workout'").
    """
    if enum_value is None:
        return ""

    # If it has a root attribute (pydantic model), use that
    if hasattr(enum_value, "root"):
        return str(enum_value.root)

    # If it's already a string, return as-is
    if isinstance(enum_value, str):
        return enum_value

    # Fallback: convert to string
    result = str(enum_value)

    # Handle cases where str() gives "root='Value'" format
    if result.startswith("root="):
        # Extract value between quotes
        match = re.search(r"root=['\"]([^'\"]+)['\"]", result)
        if match:
            return match.group(1)

    return result


@dataclass
class Activity:
    """Represents a Strava activity."""

    id: int
    name: str
    type: str
    sport_type: str
    start_date: datetime
    start_date_local: datetime
    timezone: str
    distance: float
    moving_time: int
    elapsed_time: int
    description: str | None = None
    total_elevation_gain: float | None = None
    calories: int | None = None
    average_speed: float | None = None
    max_speed: float | None = None
    average_heartrate: float | None = None
    max_heartrate: int | None = None
    average_watts: float | None = None
    max_watts: int | None = None
    average_cadence: float | None = None
    gear_id: str | None = None
    device_name: str | None = None
    trainer: bool = False
    commute: bool = False
    private: bool = False
    kudos_count: int = 0
    comment_count: int = 0
    athlete_count: int = 1
    achievement_count: int = 0
    pr_count: int = 0
    has_gps: bool = False
    has_photos: bool = False
    photo_count: int = 0
    comments: list[dict[str, Any]] = field(default_factory=list)
    kudos: list[dict[str, Any]] = field(default_factory=list)
    laps: list[dict[str, Any]] = field(default_factory=list)
    segment_efforts: list[dict[str, Any]] = field(default_factory=list)
    photos: list[dict[str, Any]] = field(default_factory=list)
    # Related sessions (same activity from different devices)
    related_sessions: list[str] = field(default_factory=list)

    @classmethod
    def from_strava_activity(cls, strava_activity: Any) -> Activity:
        """Create an Activity from a stravalib activity object.

        Args:
            strava_activity: Activity object from stravalib.

        Returns:
            Activity instance.
        """
        # stravalib uses pydantic models for enums; extract the actual value
        activity_type = _extract_enum_value(strava_activity.type)
        sport_type = _extract_enum_value(strava_activity.sport_type) or activity_type

        return cls(
            id=strava_activity.id,
            name=strava_activity.name or "Untitled",
            description=strava_activity.description,
            type=activity_type,
            sport_type=sport_type,
            start_date=strava_activity.start_date,
            start_date_local=strava_activity.start_date_local,
            timezone=str(strava_activity.timezone),
            distance=float(strava_activity.distance) if strava_activity.distance else 0.0,
            moving_time=_duration_to_seconds(strava_activity.moving_time),
            elapsed_time=_duration_to_seconds(strava_activity.elapsed_time),
            total_elevation_gain=float(strava_activity.total_elevation_gain)
            if strava_activity.total_elevation_gain
            else None,
            calories=strava_activity.calories,
            average_speed=float(strava_activity.average_speed)
            if strava_activity.average_speed
            else None,
            max_speed=float(strava_activity.max_speed) if strava_activity.max_speed else None,
            average_heartrate=strava_activity.average_heartrate,
            max_heartrate=strava_activity.max_heartrate,
            average_watts=strava_activity.average_watts,
            max_watts=strava_activity.max_watts,
            average_cadence=strava_activity.average_cadence,
            gear_id=strava_activity.gear_id,
            device_name=strava_activity.device_name,
            trainer=strava_activity.trainer or False,
            commute=strava_activity.commute or False,
            private=strava_activity.private or False,
            kudos_count=strava_activity.kudos_count or 0,
            comment_count=strava_activity.comment_count or 0,
            athlete_count=strava_activity.athlete_count or 1,
            achievement_count=strava_activity.achievement_count or 0,
            pr_count=strava_activity.pr_count or 0,
            has_gps=bool(strava_activity.start_latlng),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert activity to dictionary for JSON serialization.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "sport_type": self.sport_type,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "start_date_local": self.start_date_local.isoformat()
            if self.start_date_local
            else None,
            "timezone": self.timezone,
            "distance": self.distance,
            "moving_time": self.moving_time,
            "elapsed_time": self.elapsed_time,
            "total_elevation_gain": self.total_elevation_gain,
            "calories": self.calories,
            "average_speed": self.average_speed,
            "max_speed": self.max_speed,
            "average_heartrate": self.average_heartrate,
            "max_heartrate": self.max_heartrate,
            "average_watts": self.average_watts,
            "max_watts": self.max_watts,
            "average_cadence": self.average_cadence,
            "gear_id": self.gear_id,
            "device_name": self.device_name,
            "trainer": self.trainer,
            "commute": self.commute,
            "private": self.private,
            "kudos_count": self.kudos_count,
            "comment_count": self.comment_count,
            "athlete_count": self.athlete_count,
            "achievement_count": self.achievement_count,
            "pr_count": self.pr_count,
            "has_gps": self.has_gps,
            "has_photos": self.has_photos,
            "photo_count": self.photo_count,
            "comments": self.comments,
            "kudos": self.kudos,
            "laps": self.laps,
            "segment_efforts": self.segment_efforts,
            "photos": self.photos,
            "related_sessions": self.related_sessions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Activity:
        """Create an Activity from a dictionary.

        Args:
            data: Dictionary with activity data.

        Returns:
            Activity instance.
        """
        # Parse datetime strings
        start_date_raw = data.get("start_date")
        if isinstance(start_date_raw, str):
            start_date = datetime.fromisoformat(start_date_raw.replace("Z", "+00:00"))
        elif isinstance(start_date_raw, datetime):
            start_date = start_date_raw
        else:
            start_date = datetime.now()  # Fallback

        start_date_local_raw = data.get("start_date_local")
        if isinstance(start_date_local_raw, str):
            start_date_local = datetime.fromisoformat(start_date_local_raw)
        elif isinstance(start_date_local_raw, datetime):
            start_date_local = start_date_local_raw
        else:
            start_date_local = start_date  # Fallback to start_date

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            type=data["type"],
            sport_type=data.get("sport_type", data["type"]),
            start_date=start_date,
            start_date_local=start_date_local,
            timezone=data.get("timezone", ""),
            distance=data.get("distance", 0.0),
            moving_time=data.get("moving_time", 0),
            elapsed_time=data.get("elapsed_time", 0),
            total_elevation_gain=data.get("total_elevation_gain"),
            calories=data.get("calories"),
            average_speed=data.get("average_speed"),
            max_speed=data.get("max_speed"),
            average_heartrate=data.get("average_heartrate"),
            max_heartrate=data.get("max_heartrate"),
            average_watts=data.get("average_watts"),
            max_watts=data.get("max_watts"),
            average_cadence=data.get("average_cadence"),
            gear_id=data.get("gear_id"),
            device_name=data.get("device_name"),
            trainer=data.get("trainer", False),
            commute=data.get("commute", False),
            private=data.get("private", False),
            kudos_count=data.get("kudos_count", 0),
            comment_count=data.get("comment_count", 0),
            athlete_count=data.get("athlete_count", 1),
            achievement_count=data.get("achievement_count", 0),
            pr_count=data.get("pr_count", 0),
            has_gps=data.get("has_gps", False),
            has_photos=data.get("has_photos", False),
            photo_count=data.get("photo_count", 0),
            comments=data.get("comments", []),
            kudos=data.get("kudos", []),
            laps=data.get("laps", []),
            segment_efforts=data.get("segment_efforts", []),
            photos=data.get("photos", []),
            related_sessions=data.get("related_sessions", []),
        )


def save_activity(data_dir: Path, username: str, activity: Activity) -> Path:
    """Save activity metadata to info.json.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        activity: Activity to save.

    Returns:
        Path to saved info.json file.
    """
    session_dir = get_session_dir(data_dir, username, activity.start_date)
    session_dir.mkdir(parents=True, exist_ok=True)

    info_path = get_info_path(session_dir)
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(activity.to_dict(), f, indent=2, default=str)

    return info_path


def load_activity(session_dir: Path) -> Activity | None:
    """Load activity from info.json.

    Args:
        session_dir: Session partition directory.

    Returns:
        Activity instance or None if not found.
    """
    info_path = get_info_path(session_dir)
    if not info_path.exists():
        return None

    with open(info_path, encoding="utf-8") as f:
        data = json.load(f)

    return Activity.from_dict(data)


def load_activities(data_dir: Path, username: str) -> list[Activity]:
    """Load all activities for an athlete.

    Args:
        data_dir: Base data directory.
        username: Athlete username.

    Returns:
        List of Activity instances sorted by start date (newest first).
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    activities: list[Activity] = []

    for _, session_dir in iter_session_dirs(athlete_dir):
        activity = load_activity(session_dir)
        if activity:
            activities.append(activity)

    # Sort by start date descending
    activities.sort(key=lambda a: a.start_date, reverse=True)
    return activities


def activity_exists(data_dir: Path, username: str, start_date: datetime) -> bool:
    """Check if an activity already exists.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        start_date: Activity start date.

    Returns:
        True if activity exists.
    """
    session_dir = get_session_dir(data_dir, username, start_date)
    info_path = get_info_path(session_dir)
    return info_path.exists()


# Sessions TSV columns per data-model.md
SESSIONS_TSV_COLUMNS = [
    "datetime",
    "datetime_local",  # Local time for display (Activity Timing heatmap)
    "type",
    "sport",
    "name",
    "distance_m",
    "moving_time_s",
    "elapsed_time_s",
    "elevation_gain_m",
    "calories",
    "avg_hr",
    "max_hr",
    "avg_watts",
    "gear_id",
    "athletes",
    "kudos_count",
    "comment_count",
    "has_gps",
    "photos_path",  # Path to photos folder if photos exist, empty otherwise
    "photo_count",
    "start_lat",  # Starting point latitude (first GPS coordinate)
    "start_lng",  # Starting point longitude (first GPS coordinate)
]


def update_sessions_tsv(
    data_dir: Path, username: str, use_timezone_history: bool = True
) -> Path:
    """Regenerate sessions.tsv from all activity info.json files.

    Args:
        data_dir: Base data directory.
        username: Athlete username.
        use_timezone_history: If True, use timezone history for local time correction.

    Returns:
        Path to sessions.tsv file.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    athlete_dir.mkdir(parents=True, exist_ok=True)

    sessions_path = get_sessions_tsv_path(athlete_dir)

    # Try to load timezone history for local time correction
    tz_history = None
    if use_timezone_history:
        try:
            from mykrok.services.timezone import TimezoneHistory

            history_path = athlete_dir / "timezone-history.tsv"
            if history_path.exists():
                tz_history = TimezoneHistory(athlete_dir)
        except ImportError:
            pass  # timezone module not available

    # Collect all activities
    activities = load_activities(data_dir, username)

    # Sort chronologically for TSV (oldest first)
    activities.sort(key=lambda a: a.start_date)

    # Write TSV
    with open(sessions_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SESSIONS_TSV_COLUMNS, delimiter="\t")
        writer.writeheader()

        for activity in activities:
            # Build photos_path: ses={datetime}/photos/ if photos exist, empty otherwise
            session_key = activity.start_date.strftime("%Y%m%dT%H%M%S")
            photos_path = f"ses={session_key}/photos/" if activity.has_photos else ""

            # Get start coordinates from tracking data
            start_lat = ""
            start_lng = ""
            if activity.has_gps:
                session_dir = athlete_dir / f"ses={session_key}"
                manifest = load_tracking_manifest(session_dir)
                if manifest and manifest.has_gps:
                    coords = get_coordinates(session_dir)
                    if coords:
                        start_lat = str(round(coords[0][0], 6))
                        start_lng = str(round(coords[0][1], 6))

            # Local time for Activity Timing heatmap
            # Priority: 1) timezone history, 2) Strava's start_date_local, 3) UTC
            if tz_history is not None:
                # Use corrected local time from timezone history
                corrected_local = tz_history.get_local_time(activity.start_date)
                datetime_local = corrected_local.strftime("%Y%m%dT%H%M%S")
            elif activity.start_date_local:
                # Fall back to Strava's local time
                datetime_local = activity.start_date_local.strftime("%Y%m%dT%H%M%S")
            else:
                # Last resort: use UTC
                datetime_local = session_key

            writer.writerow(
                {
                    "datetime": session_key,
                    "datetime_local": datetime_local,
                    "type": activity.type,
                    "sport": activity.sport_type,
                    "name": activity.name,
                    "distance_m": activity.distance,
                    "moving_time_s": activity.moving_time,
                    "elapsed_time_s": activity.elapsed_time,
                    "elevation_gain_m": activity.total_elevation_gain or "",
                    "calories": activity.calories or "",
                    "avg_hr": activity.average_heartrate or "",
                    "max_hr": activity.max_heartrate or "",
                    "avg_watts": activity.average_watts or "",
                    "gear_id": activity.gear_id or "",
                    "athletes": activity.athlete_count,
                    "kudos_count": activity.kudos_count,
                    "comment_count": activity.comment_count,
                    "has_gps": "true" if activity.has_gps else "false",
                    "photos_path": photos_path,
                    "photo_count": activity.photo_count,
                    "start_lat": start_lat,
                    "start_lng": start_lng,
                }
            )

    return sessions_path


def read_sessions_tsv(data_dir: Path, username: str) -> list[dict[str, Any]]:
    """Read sessions.tsv file.

    Args:
        data_dir: Base data directory.
        username: Athlete username.

    Returns:
        List of session dictionaries.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    sessions_path = get_sessions_tsv_path(athlete_dir)

    if not sessions_path.exists():
        return []

    sessions: list[dict[str, Any]] = []
    with open(sessions_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # Convert types
            session = dict(row)
            session["distance_m"] = float(row["distance_m"]) if row["distance_m"] else 0.0
            session["moving_time_s"] = int(row["moving_time_s"]) if row["moving_time_s"] else 0
            session["elapsed_time_s"] = int(row["elapsed_time_s"]) if row["elapsed_time_s"] else 0
            session["elevation_gain_m"] = (
                float(row["elevation_gain_m"]) if row["elevation_gain_m"] else None
            )
            session["calories"] = int(row["calories"]) if row["calories"] else None
            session["avg_hr"] = float(row["avg_hr"]) if row["avg_hr"] else None
            session["max_hr"] = int(row["max_hr"]) if row["max_hr"] else None
            session["avg_watts"] = float(row["avg_watts"]) if row["avg_watts"] else None
            session["athletes"] = int(row["athletes"]) if row["athletes"] else 1
            session["kudos_count"] = int(row["kudos_count"]) if row["kudos_count"] else 0
            session["comment_count"] = int(row["comment_count"]) if row["comment_count"] else 0
            session["has_gps"] = row["has_gps"].lower() == "true"
            # photos_path is non-empty if photos exist
            photos_path = row.get("photos_path", "")
            session["photos_path"] = photos_path
            session["has_photos"] = bool(photos_path)
            session["photo_count"] = int(row["photo_count"]) if row["photo_count"] else 0
            sessions.append(session)

    return sessions
