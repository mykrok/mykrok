"""GPS/sensor stream handling for MyKrok.

Handles storage and retrieval of time-series tracking data (GPS coordinates,
heart rate, cadence, power, etc.) in Parquet format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mykrok.lib.parquet import (
    convert_strava_streams_to_tracking,
    get_tracking_metadata,
    read_tracking_columns,
    read_tracking_data,
    safe_remove_for_overwrite,
    tracking_to_coordinates,
    write_tracking_data,
)
from mykrok.lib.paths import (
    get_tracking_manifest_path,
    get_tracking_parquet_path,
)


@dataclass
class TrackingManifest:
    """Metadata about tracking data for an activity."""

    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    has_gps: bool = False
    has_hr: bool = False
    has_power: bool = False
    has_cadence: bool = False
    has_altitude: bool = False
    has_temp: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "columns": self.columns,
            "row_count": self.row_count,
            "has_gps": self.has_gps,
            "has_hr": self.has_hr,
            "has_power": self.has_power,
            "has_cadence": self.has_cadence,
            "has_altitude": self.has_altitude,
            "has_temp": self.has_temp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrackingManifest:
        """Create from dictionary.

        Args:
            data: Dictionary with manifest data.

        Returns:
            TrackingManifest instance.
        """
        return cls(
            columns=data.get("columns", []),
            row_count=data.get("row_count", 0),
            has_gps=data.get("has_gps", False),
            has_hr=data.get("has_hr", False),
            has_power=data.get("has_power", False),
            has_cadence=data.get("has_cadence", False),
            has_altitude=data.get("has_altitude", False),
            has_temp=data.get("has_temp", False),
        )


def save_tracking_data(
    session_dir: Path,
    streams: dict[str, Any],
) -> tuple[Path, TrackingManifest]:
    """Save Strava stream data to Parquet format.

    Args:
        session_dir: Session partition directory.
        streams: Stream data from Strava API.

    Returns:
        Tuple of (parquet_path, manifest).
    """
    session_dir.mkdir(parents=True, exist_ok=True)

    # Convert Strava stream format to tracking format
    tracking_data = convert_strava_streams_to_tracking(streams)

    # Determine which columns have data
    manifest = TrackingManifest()
    manifest.columns = list(tracking_data.keys())

    if tracking_data:
        # Check for GPS data
        if "lat" in tracking_data and "lng" in tracking_data:
            has_valid_gps = any(
                lat is not None and lng is not None
                for lat, lng in zip(tracking_data["lat"], tracking_data["lng"], strict=False)
            )
            manifest.has_gps = has_valid_gps

        # Check for other sensors
        manifest.has_hr = "heartrate" in tracking_data and any(
            v is not None for v in tracking_data["heartrate"]
        )
        manifest.has_power = "watts" in tracking_data and any(
            v is not None for v in tracking_data["watts"]
        )
        manifest.has_cadence = "cadence" in tracking_data and any(
            v is not None for v in tracking_data["cadence"]
        )
        manifest.has_altitude = "altitude" in tracking_data and any(
            v is not None for v in tracking_data["altitude"]
        )
        manifest.has_temp = "temp" in tracking_data and any(
            v is not None for v in tracking_data["temp"]
        )

    # Write Parquet file
    parquet_path = get_tracking_parquet_path(session_dir)
    manifest.row_count = write_tracking_data(parquet_path, tracking_data)

    # Write manifest (remove first to handle git-annex locked files)
    manifest_path = get_tracking_manifest_path(session_dir)
    safe_remove_for_overwrite(manifest_path)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)

    return parquet_path, manifest


def load_tracking_manifest(session_dir: Path) -> TrackingManifest | None:
    """Load tracking manifest from session directory.

    Args:
        session_dir: Session partition directory.

    Returns:
        TrackingManifest or None if not found.
    """
    manifest_path = get_tracking_manifest_path(session_dir)
    if not manifest_path.exists():
        return None

    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    return TrackingManifest.from_dict(data)


def has_tracking_data(session_dir: Path) -> bool:
    """Check if tracking data exists for a session.

    Args:
        session_dir: Session partition directory.

    Returns:
        True if tracking.parquet exists.
    """
    return get_tracking_parquet_path(session_dir).exists()


def get_coordinates(session_dir: Path) -> list[tuple[float, float]]:
    """Get GPS coordinates from tracking data.

    Args:
        session_dir: Session partition directory.

    Returns:
        List of (lat, lng) tuples.
    """
    parquet_path = get_tracking_parquet_path(session_dir)
    if not parquet_path.exists():
        return []

    return tracking_to_coordinates(parquet_path)


def get_tracking_with_sensors(
    session_dir: Path,
    include_hr: bool = True,
    include_cadence: bool = True,
    include_power: bool = True,
) -> list[dict[str, Any]]:
    """Get tracking data with sensor values as list of point dictionaries.

    Args:
        session_dir: Session partition directory.
        include_hr: Include heart rate.
        include_cadence: Include cadence.
        include_power: Include power.

    Returns:
        List of point dictionaries with requested data.
    """
    parquet_path = get_tracking_parquet_path(session_dir)
    if not parquet_path.exists():
        return []

    # Build column list
    columns = ["time", "lat", "lng", "altitude"]
    if include_hr:
        columns.append("heartrate")
    if include_cadence:
        columns.append("cadence")
    if include_power:
        columns.append("watts")

    table = read_tracking_columns(parquet_path, columns)
    points: list[dict[str, Any]] = []

    for i in range(table.num_rows):
        point: dict[str, Any] = {}
        for col_name in columns:
            if col_name in table.column_names:
                value = table.column(col_name)[i].as_py()
                point[col_name] = value
        points.append(point)

    return points


def get_all_tracking_data(session_dir: Path) -> dict[str, list[Any]]:
    """Get all tracking data as dictionary of arrays.

    Args:
        session_dir: Session partition directory.

    Returns:
        Dictionary mapping column names to value lists.
    """
    parquet_path = get_tracking_parquet_path(session_dir)
    if not parquet_path.exists():
        return {}

    table = read_tracking_data(parquet_path)
    result: dict[str, list[Any]] = {}

    for col_name in table.column_names:
        result[col_name] = table.column(col_name).to_pylist()

    return result


def get_tracking_stats(session_dir: Path) -> dict[str, Any]:
    """Get statistics about tracking data.

    Args:
        session_dir: Session partition directory.

    Returns:
        Dictionary with tracking statistics.
    """
    parquet_path = get_tracking_parquet_path(session_dir)
    if not parquet_path.exists():
        return {}

    try:
        return get_tracking_metadata(parquet_path)
    except Exception:
        return {}


@dataclass
class TrackPoint:
    """A single point in a GPS track with optional sensor data."""

    time: float
    lat: float | None = None
    lng: float | None = None
    altitude: float | None = None
    distance: float | None = None
    heartrate: int | None = None
    cadence: int | None = None
    watts: int | None = None
    temp: float | None = None

    @property
    def has_location(self) -> bool:
        """Check if point has valid GPS coordinates."""
        return self.lat is not None and self.lng is not None


def iter_track_points(session_dir: Path) -> list[TrackPoint]:
    """Iterate over track points in a session.

    Args:
        session_dir: Session partition directory.

    Yields:
        TrackPoint instances.
    """
    data = get_all_tracking_data(session_dir)
    if not data:
        return []

    points: list[TrackPoint] = []
    row_count = len(data.get("time", []))

    def safe_get(col: str, idx: int) -> Any:
        """Get value at index, returning None if column missing or index out of bounds."""
        values = data.get(col)
        if values is None or idx >= len(values):
            return None
        return values[idx]

    for i in range(row_count):
        point = TrackPoint(
            time=safe_get("time", i) or 0.0,
            lat=safe_get("lat", i),
            lng=safe_get("lng", i),
            altitude=safe_get("altitude", i),
            distance=safe_get("distance", i),
            heartrate=safe_get("heartrate", i),
            cadence=safe_get("cadence", i),
            watts=safe_get("watts", i),
            temp=safe_get("temp", i),
        )
        points.append(point)

    return points
