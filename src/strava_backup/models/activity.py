"""Activity model and storage operations.

Handles activity metadata storage, retrieval, and sessions.tsv summary generation.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from strava_backup.lib.paths import (
    get_athlete_dir,
    get_info_path,
    get_session_dir,
    get_sessions_tsv_path,
    iter_session_dirs,
)


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

    @classmethod
    def from_strava_activity(cls, strava_activity: Any) -> Activity:
        """Create an Activity from a stravalib activity object.

        Args:
            strava_activity: Activity object from stravalib.

        Returns:
            Activity instance.
        """
        return cls(
            id=strava_activity.id,
            name=strava_activity.name or "Untitled",
            description=strava_activity.description,
            type=str(strava_activity.type),
            sport_type=str(strava_activity.sport_type) if strava_activity.sport_type else str(strava_activity.type),
            start_date=strava_activity.start_date,
            start_date_local=strava_activity.start_date_local,
            timezone=str(strava_activity.timezone),
            distance=float(strava_activity.distance) if strava_activity.distance else 0.0,
            moving_time=int(strava_activity.moving_time.total_seconds()) if strava_activity.moving_time else 0,
            elapsed_time=int(strava_activity.elapsed_time.total_seconds()) if strava_activity.elapsed_time else 0,
            total_elevation_gain=float(strava_activity.total_elevation_gain) if strava_activity.total_elevation_gain else None,
            calories=strava_activity.calories,
            average_speed=float(strava_activity.average_speed) if strava_activity.average_speed else None,
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
            "start_date_local": self.start_date_local.isoformat() if self.start_date_local else None,
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
        start_date = data.get("start_date")
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))

        start_date_local = data.get("start_date_local")
        if isinstance(start_date_local, str):
            start_date_local = datetime.fromisoformat(start_date_local)

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
    with open(info_path, "w") as f:
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

    with open(info_path) as f:
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
    "has_photos",
    "photo_count",
]


def update_sessions_tsv(data_dir: Path, username: str) -> Path:
    """Regenerate sessions.tsv from all activity info.json files.

    Args:
        data_dir: Base data directory.
        username: Athlete username.

    Returns:
        Path to sessions.tsv file.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    athlete_dir.mkdir(parents=True, exist_ok=True)

    sessions_path = get_sessions_tsv_path(athlete_dir)

    # Collect all activities
    activities = load_activities(data_dir, username)

    # Sort chronologically for TSV (oldest first)
    activities.sort(key=lambda a: a.start_date)

    # Write TSV
    with open(sessions_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SESSIONS_TSV_COLUMNS, delimiter="\t")
        writer.writeheader()

        for activity in activities:
            writer.writerow({
                "datetime": activity.start_date.strftime("%Y%m%dT%H%M%S"),
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
                "has_photos": "true" if activity.has_photos else "false",
                "photo_count": activity.photo_count,
            })

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
    with open(sessions_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            # Convert types
            session = dict(row)
            session["distance_m"] = float(row["distance_m"]) if row["distance_m"] else 0.0
            session["moving_time_s"] = int(row["moving_time_s"]) if row["moving_time_s"] else 0
            session["elapsed_time_s"] = int(row["elapsed_time_s"]) if row["elapsed_time_s"] else 0
            session["elevation_gain_m"] = float(row["elevation_gain_m"]) if row["elevation_gain_m"] else None
            session["calories"] = int(row["calories"]) if row["calories"] else None
            session["avg_hr"] = float(row["avg_hr"]) if row["avg_hr"] else None
            session["max_hr"] = int(row["max_hr"]) if row["max_hr"] else None
            session["avg_watts"] = float(row["avg_watts"]) if row["avg_watts"] else None
            session["athletes"] = int(row["athletes"]) if row["athletes"] else 1
            session["kudos_count"] = int(row["kudos_count"]) if row["kudos_count"] else 0
            session["comment_count"] = int(row["comment_count"]) if row["comment_count"] else 0
            session["has_gps"] = row["has_gps"].lower() == "true"
            session["has_photos"] = row["has_photos"].lower() == "true"
            session["photo_count"] = int(row["photo_count"]) if row["photo_count"] else 0
            sessions.append(session)

    return sessions
