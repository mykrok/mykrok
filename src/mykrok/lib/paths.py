"""Hive-partitioned path helpers for MyKrok.

Manages the directory structure for storing activities:
    data/
    ├── athletes.tsv
    └── athl={username}/
        ├── sessions.tsv
        ├── gear.json
        ├── exports/
        │   └── fittrackee.json
        └── ses={datetime}/
            ├── info.json
            ├── tracking.parquet
            ├── tracking.json
            └── photos/
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Partition prefixes
ATHLETE_PREFIX = "athl="
ATHLETE_PREFIX_LEGACY = "sub="  # Legacy prefix, used only for migration detection
SESSION_PREFIX = "ses="

if TYPE_CHECKING:
    from collections.abc import Iterator


# Session datetime format: ISO 8601 basic format without separators
# Example: 20251218T063000 for 2025-12-18 06:30:00
SESSION_DATETIME_FORMAT = "%Y%m%dT%H%M%S"


def get_athlete_dir(data_dir: Path, username: str) -> Path:
    """Get the athlete's data directory.

    Args:
        data_dir: Base data directory.
        username: Strava username (URL-safe).

    Returns:
        Path to athlete's partition directory.
    """
    return data_dir / f"{ATHLETE_PREFIX}{username}"


def get_athletes_tsv_path(data_dir: Path) -> Path:
    """Get path to top-level athletes.tsv file.

    Args:
        data_dir: Base data directory.

    Returns:
        Path to athletes.tsv.
    """
    return data_dir / "athletes.tsv"


def get_athlete_json_path(athlete_dir: Path) -> Path:
    """Get path to athlete.json profile file.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to athlete.json.
    """
    return athlete_dir / "athlete.json"


def get_avatar_path(athlete_dir: Path, ext: str = "jpg") -> Path:
    """Get path to athlete avatar image.

    Args:
        athlete_dir: Athlete partition directory.
        ext: Image file extension (default: jpg).

    Returns:
        Path to avatar image.
    """
    return athlete_dir / f"avatar.{ext}"


def get_session_dir(data_dir: Path, username: str, start_date: datetime) -> Path:
    """Get the session directory for an activity.

    Args:
        data_dir: Base data directory.
        username: Strava username.
        start_date: Activity start datetime (UTC).

    Returns:
        Path to session partition directory.
    """
    athlete_dir = get_athlete_dir(data_dir, username)
    session_key = format_session_datetime(start_date)
    return athlete_dir / f"ses={session_key}"


def format_session_datetime(dt: datetime) -> str:
    """Format datetime as session directory key.

    Args:
        dt: Datetime to format.

    Returns:
        ISO 8601 basic format string (e.g., '20251218T063000').
    """
    return dt.strftime(SESSION_DATETIME_FORMAT)


def parse_session_datetime(session_key: str) -> datetime:
    """Parse session directory key back to datetime.

    Args:
        session_key: Session key string (e.g., '20251218T063000').

    Returns:
        Parsed datetime object.
    """
    return datetime.strptime(session_key, SESSION_DATETIME_FORMAT)


def get_info_path(session_dir: Path) -> Path:
    """Get path to activity info.json file.

    Args:
        session_dir: Session partition directory.

    Returns:
        Path to info.json.
    """
    return session_dir / "info.json"


def get_tracking_parquet_path(session_dir: Path) -> Path:
    """Get path to tracking.parquet file.

    Args:
        session_dir: Session partition directory.

    Returns:
        Path to tracking.parquet.
    """
    return session_dir / "tracking.parquet"


def get_tracking_manifest_path(session_dir: Path) -> Path:
    """Get path to tracking.json manifest file.

    Args:
        session_dir: Session partition directory.

    Returns:
        Path to tracking.json.
    """
    return session_dir / "tracking.json"


def get_photos_dir(session_dir: Path) -> Path:
    """Get path to photos directory.

    Args:
        session_dir: Session partition directory.

    Returns:
        Path to photos/ directory.
    """
    return session_dir / "photos"


def get_sessions_tsv_path(athlete_dir: Path) -> Path:
    """Get path to sessions.tsv summary file.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to sessions.tsv.
    """
    return athlete_dir / "sessions.tsv"


def get_gear_json_path(athlete_dir: Path) -> Path:
    """Get path to gear.json catalog.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to gear.json.
    """
    return athlete_dir / "gear.json"


def get_exports_dir(athlete_dir: Path) -> Path:
    """Get path to exports directory.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to exports/ directory.
    """
    return athlete_dir / "exports"


def get_fittrackee_export_path(athlete_dir: Path) -> Path:
    """Get path to FitTrackee export state file.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to exports/fittrackee.json.
    """
    return get_exports_dir(athlete_dir) / "fittrackee.json"


def ensure_session_dir(data_dir: Path, username: str, start_date: datetime) -> Path:
    """Create session directory if it doesn't exist.

    Args:
        data_dir: Base data directory.
        username: Strava username.
        start_date: Activity start datetime.

    Returns:
        Path to created session directory.
    """
    session_dir = get_session_dir(data_dir, username, start_date)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def ensure_photos_dir(session_dir: Path) -> Path:
    """Create photos directory if it doesn't exist.

    Args:
        session_dir: Session partition directory.

    Returns:
        Path to created photos directory.
    """
    photos_dir = get_photos_dir(session_dir)
    photos_dir.mkdir(parents=True, exist_ok=True)
    return photos_dir


def ensure_exports_dir(athlete_dir: Path) -> Path:
    """Create exports directory if it doesn't exist.

    Args:
        athlete_dir: Athlete partition directory.

    Returns:
        Path to created exports directory.
    """
    exports_dir = get_exports_dir(athlete_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)
    return exports_dir


def iter_session_dirs(athlete_dir: Path) -> Iterator[tuple[str, Path]]:
    """Iterate over all session directories for an athlete.

    Args:
        athlete_dir: Athlete partition directory.

    Yields:
        Tuples of (session_key, session_path) sorted by session key (chronological).
    """
    if not athlete_dir.exists():
        return

    sessions: list[tuple[str, Path]] = []
    for entry in athlete_dir.iterdir():
        if entry.is_dir() and entry.name.startswith("ses="):
            session_key = entry.name[4:]  # Remove 'ses=' prefix
            sessions.append((session_key, entry))

    # Sort chronologically
    sessions.sort(key=lambda x: x[0])
    yield from sessions


def iter_athlete_dirs(data_dir: Path) -> Iterator[tuple[str, Path]]:
    """Iterate over all athlete directories.

    Only looks for athl= prefixes. Run 'mykrok migrate' first if you have
    legacy sub= directories.

    Args:
        data_dir: Base data directory.

    Yields:
        Tuples of (username, athlete_path).
    """
    if not data_dir.exists():
        return

    for entry in data_dir.iterdir():
        if entry.is_dir() and entry.name.startswith(ATHLETE_PREFIX):
            username = entry.name[len(ATHLETE_PREFIX) :]
            yield (username, entry)


def get_photo_path(photos_dir: Path, photo_datetime: datetime, extension: str = "jpg") -> Path:
    """Get path for a photo file.

    Args:
        photos_dir: Photos directory.
        photo_datetime: Photo timestamp.
        extension: File extension (without dot).

    Returns:
        Path to photo file.
    """
    filename = f"{format_session_datetime(photo_datetime)}.{extension}"
    return photos_dir / filename


def extract_session_key_from_path(path: Path) -> str | None:
    """Extract session key from a path.

    Args:
        path: Path that may contain a session directory.

    Returns:
        Session key if found, None otherwise.
    """
    for part in path.parts:
        if part.startswith("ses="):
            return part[4:]
    return None


def extract_username_from_path(path: Path) -> str | None:
    """Extract username from a path.

    Args:
        path: Path that may contain an athlete directory.

    Returns:
        Username if found, None otherwise.
    """
    for part in path.parts:
        if part.startswith(ATHLETE_PREFIX):
            return part[len(ATHLETE_PREFIX) :]
    return None


def needs_migration(data_dir: Path) -> bool:
    """Check if data directory has legacy sub= prefixes that need migration.

    Args:
        data_dir: Base data directory.

    Returns:
        True if any sub= directories exist.
    """
    if not data_dir.exists():
        return False

    for entry in data_dir.iterdir():
        if entry.is_dir() and entry.name.startswith(ATHLETE_PREFIX_LEGACY):
            return True
    return False
