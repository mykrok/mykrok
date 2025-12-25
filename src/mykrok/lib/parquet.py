"""Parquet utilities for MyKrok.

Provides schema definitions and streaming write functionality for
GPS/sensor time-series data storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.parquet as pq

if TYPE_CHECKING:
    from collections.abc import Iterator


def safe_remove_for_overwrite(path: Path) -> None:
    """Remove a file before overwriting to handle git-annex locked files.

    Git-annex locked files are symlinks to read-only objects in .git/annex/objects/.
    Attempting to write to them directly fails. Removing the symlink first and
    then writing a new file avoids this issue without needing to unlock.

    Args:
        path: File path to remove if it exists.
    """
    if path.exists() or path.is_symlink():
        path.unlink()


# Schema for tracking data (GPS and sensors)
TRACKING_SCHEMA = pa.schema(
    [
        ("time", pa.float64()),  # Seconds from activity start
        ("lat", pa.float64()),  # GPS latitude in decimal degrees
        ("lng", pa.float64()),  # GPS longitude in decimal degrees
        ("altitude", pa.float32()),  # Elevation in meters
        ("distance", pa.float32()),  # Cumulative distance in meters
        ("heartrate", pa.int16()),  # Heart rate in BPM
        ("cadence", pa.int16()),  # Cadence (RPM or SPM)
        ("watts", pa.int16()),  # Power in watts
        ("temp", pa.float32()),  # Temperature in Celsius
        ("velocity_smooth", pa.float32()),  # Smoothed velocity in m/s
        ("grade_smooth", pa.float32()),  # Smoothed grade percentage
    ]
)


def get_tracking_schema() -> pa.Schema:
    """Get the schema for tracking data.

    Returns:
        PyArrow schema for tracking.parquet files.
    """
    return TRACKING_SCHEMA


def write_tracking_data(
    path: Path,
    data: dict[str, list[Any]],
    compression: str = "snappy",
) -> int:
    """Write tracking data to a Parquet file.

    Args:
        path: Output path for the Parquet file.
        data: Dictionary mapping column names to lists of values.
        compression: Compression codec (default: snappy).

    Returns:
        Number of rows written.
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Prepare arrays for each column
    arrays: dict[str, pa.Array] = {}
    row_count = 0

    for field in TRACKING_SCHEMA:
        col_name = field.name
        if col_name in data and data[col_name]:
            values = data[col_name]
            row_count = max(row_count, len(values))
            arrays[col_name] = pa.array(values, type=field.type)
        else:
            # Column not present, will be filled with nulls
            arrays[col_name] = None

    # If we have no data, return early
    if row_count == 0:
        return 0

    # Fill missing columns with nulls
    for field in TRACKING_SCHEMA:
        if arrays.get(field.name) is None:
            arrays[field.name] = pa.nulls(row_count, type=field.type)

    # Create table with ordered columns
    table = pa.table(
        {field.name: arrays[field.name] for field in TRACKING_SCHEMA},
        schema=TRACKING_SCHEMA,
    )

    # Remove existing file first to handle git-annex locked symlinks
    safe_remove_for_overwrite(path)

    # Write to Parquet
    pq.write_table(
        table,
        path,
        compression=compression,
        use_dictionary=True,
        row_group_size=10000,
        version="2.6",
    )

    return row_count


def write_tracking_data_streaming(
    path: Path,
    data_iterator: Iterator[dict[str, list[Any]]],
    compression: str = "snappy",
    _batch_size: int = 10000,
) -> int:
    """Write tracking data to Parquet using streaming writes.

    Use this for large datasets to maintain bounded memory usage.

    Args:
        path: Output path for the Parquet file.
        data_iterator: Iterator yielding batches of data.
        compression: Compression codec (default: snappy).
        batch_size: Number of rows per batch.

    Returns:
        Total number of rows written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing file first to handle git-annex locked symlinks
    safe_remove_for_overwrite(path)

    total_rows = 0

    writer: pq.ParquetWriter | None = None
    try:
        for batch_data in data_iterator:
            if not batch_data:
                continue

            # Convert batch to table
            arrays = {}
            row_count = 0

            for field in TRACKING_SCHEMA:
                col_name = field.name
                if col_name in batch_data and batch_data[col_name]:
                    values = batch_data[col_name]
                    row_count = max(row_count, len(values))
                    arrays[col_name] = pa.array(values, type=field.type)

            if row_count == 0:
                continue

            # Fill missing columns
            for field in TRACKING_SCHEMA:
                if field.name not in arrays:
                    arrays[field.name] = pa.nulls(row_count, type=field.type)

            batch_table = pa.table(
                {field.name: arrays[field.name] for field in TRACKING_SCHEMA},
                schema=TRACKING_SCHEMA,
            )

            # Initialize writer on first batch
            if writer is None:
                writer = pq.ParquetWriter(
                    path,
                    TRACKING_SCHEMA,
                    compression=compression,
                    use_dictionary=True,
                    version="2.6",
                )

            writer.write_table(batch_table)
            total_rows += row_count

    finally:
        if writer is not None:
            writer.close()

    return total_rows


def read_tracking_data(path: Path) -> pa.Table:
    """Read tracking data from a Parquet file.

    Args:
        path: Path to Parquet file.

    Returns:
        PyArrow table with tracking data.
    """
    return pq.read_table(path)


def read_tracking_columns(path: Path, columns: list[str]) -> pa.Table:
    """Read specific columns from tracking data.

    Args:
        path: Path to Parquet file.
        columns: List of column names to read.

    Returns:
        PyArrow table with requested columns.
    """
    return pq.read_table(path, columns=columns)


def get_tracking_metadata(path: Path) -> dict[str, Any]:
    """Get metadata about a tracking file without reading all data.

    Args:
        path: Path to Parquet file.

    Returns:
        Dictionary with file metadata.
    """
    parquet_file = pq.ParquetFile(path)
    metadata = parquet_file.metadata

    return {
        "row_count": metadata.num_rows,
        "row_groups": metadata.num_row_groups,
        "columns": [col.name for col in parquet_file.schema_arrow],
        "created_by": metadata.created_by,
        "format_version": str(metadata.format_version),
    }


def convert_strava_streams_to_tracking(
    streams: dict[str, Any],
) -> dict[str, list[Any]]:
    """Convert Strava API stream data to tracking format.

    Args:
        streams: Dictionary of stream data from Strava API.

    Returns:
        Dictionary formatted for write_tracking_data.
    """
    result: dict[str, list[Any]] = {}

    # Direct mappings
    if "time" in streams:
        result["time"] = [float(t) for t in streams["time"]]

    if "altitude" in streams:
        result["altitude"] = [float(a) if a is not None else None for a in streams["altitude"]]

    if "distance" in streams:
        result["distance"] = [float(d) if d is not None else None for d in streams["distance"]]

    if "heartrate" in streams:
        result["heartrate"] = [int(h) if h is not None else None for h in streams["heartrate"]]

    if "cadence" in streams:
        result["cadence"] = [int(c) if c is not None else None for c in streams["cadence"]]

    if "watts" in streams:
        result["watts"] = [int(w) if w is not None else None for w in streams["watts"]]

    if "temp" in streams:
        result["temp"] = [float(t) if t is not None else None for t in streams["temp"]]

    if "velocity_smooth" in streams:
        result["velocity_smooth"] = [
            float(v) if v is not None else None for v in streams["velocity_smooth"]
        ]

    if "grade_smooth" in streams:
        result["grade_smooth"] = [
            float(g) if g is not None else None for g in streams["grade_smooth"]
        ]

    # Handle latlng which is a list of [lat, lng] pairs
    if "latlng" in streams:
        latlng = streams["latlng"]
        result["lat"] = [float(coord[0]) if coord else None for coord in latlng]
        result["lng"] = [float(coord[1]) if coord else None for coord in latlng]

    return result


def tracking_to_coordinates(path: Path) -> list[tuple[float, float]]:
    """Extract GPS coordinates from tracking file.

    Args:
        path: Path to Parquet file.

    Returns:
        List of (lat, lng) tuples.
    """
    table = read_tracking_columns(path, ["lat", "lng"])
    coords: list[tuple[float, float]] = []

    lat_col = table.column("lat")
    lng_col = table.column("lng")

    for i in range(len(lat_col)):
        lat = lat_col[i].as_py()
        lng = lng_col[i].as_py()
        if lat is not None and lng is not None:
            coords.append((lat, lng))

    return coords
