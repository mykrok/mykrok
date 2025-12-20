"""Migration utilities for strava-backup.

Handles data format migrations between versions.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from strava_backup.lib.paths import (
    ATHLETE_PREFIX,
    ATHLETE_PREFIX_LEGACY,
    get_athletes_tsv_path,
    get_sessions_tsv_path,
    iter_athlete_dirs,
    iter_session_dirs,
    needs_migration,
)
from strava_backup.models.activity import load_activity
from strava_backup.models.tracking import get_coordinates, load_tracking_manifest


def migrate_athlete_prefixes(data_dir: Path, dry_run: bool = False) -> list[tuple[Path, Path]]:
    """Migrate athlete directories from sub= to athl= prefix.

    Args:
        data_dir: Base data directory.
        dry_run: If True, only report what would be done.

    Returns:
        List of (old_path, new_path) tuples for renamed directories.
    """
    renames: list[tuple[Path, Path]] = []

    if not data_dir.exists():
        return renames

    for entry in data_dir.iterdir():
        if entry.is_dir() and entry.name.startswith(ATHLETE_PREFIX_LEGACY):
            username = entry.name[len(ATHLETE_PREFIX_LEGACY):]
            new_path = data_dir / f"{ATHLETE_PREFIX}{username}"

            if new_path.exists():
                raise ValueError(
                    f"Cannot migrate {entry} -> {new_path}: destination already exists"
                )

            renames.append((entry, new_path))

            if not dry_run:
                entry.rename(new_path)

    return renames


def generate_athletes_tsv(data_dir: Path) -> Path:
    """Generate top-level athletes.tsv file.

    Columns:
        username, session_count, first_activity, last_activity, total_distance_km,
        total_moving_time_h, activity_types

    Args:
        data_dir: Base data directory.

    Returns:
        Path to generated athletes.tsv.
    """
    athletes_path = get_athletes_tsv_path(data_dir)

    rows: list[dict[str, Any]] = []

    for username, athlete_dir in iter_athlete_dirs(data_dir):
        sessions_path = get_sessions_tsv_path(athlete_dir)

        session_count = 0
        first_activity = None
        last_activity = None
        total_distance_m = 0.0
        total_moving_time_s = 0
        activity_types: set[str] = set()

        if sessions_path.exists():
            with open(sessions_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    session_count += 1

                    # Track date range
                    dt = row.get("datetime", "")
                    if dt:
                        if first_activity is None or dt < first_activity:
                            first_activity = dt
                        if last_activity is None or dt > last_activity:
                            last_activity = dt

                    # Accumulate totals
                    try:
                        total_distance_m += float(row.get("distance_m", 0) or 0)
                    except ValueError:
                        pass

                    try:
                        total_moving_time_s += int(row.get("moving_time_s", 0) or 0)
                    except ValueError:
                        pass

                    # Collect activity types
                    sport = row.get("sport", "")
                    if sport:
                        activity_types.add(sport)

        rows.append({
            "username": username,
            "session_count": session_count,
            "first_activity": first_activity or "",
            "last_activity": last_activity or "",
            "total_distance_km": round(total_distance_m / 1000, 1),
            "total_moving_time_h": round(total_moving_time_s / 3600, 1),
            "activity_types": ",".join(sorted(activity_types)),
        })

    # Write TSV
    fieldnames = [
        "username",
        "session_count",
        "first_activity",
        "last_activity",
        "total_distance_km",
        "total_moving_time_h",
        "activity_types",
    ]

    with open(athletes_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    return athletes_path


def add_center_coords_to_sessions(data_dir: Path) -> int:
    """Add center GPS coordinates to sessions.tsv files.

    Adds center_lat and center_lng columns if not present.

    Args:
        data_dir: Base data directory.

    Returns:
        Number of sessions updated.
    """
    updated_count = 0

    for username, athlete_dir in iter_athlete_dirs(data_dir):
        sessions_path = get_sessions_tsv_path(athlete_dir)
        if not sessions_path.exists():
            continue

        # Read existing sessions
        with open(sessions_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        # Check if center coords already exist
        if "center_lat" in fieldnames and "center_lng" in fieldnames:
            continue

        # Add new columns
        if "center_lat" not in fieldnames:
            fieldnames.append("center_lat")
        if "center_lng" not in fieldnames:
            fieldnames.append("center_lng")

        # Calculate center coords for each session
        for row in rows:
            session_key = row.get("datetime", "")
            if not session_key:
                row["center_lat"] = ""
                row["center_lng"] = ""
                continue

            session_dir = athlete_dir / f"ses={session_key}"
            if not session_dir.exists():
                row["center_lat"] = ""
                row["center_lng"] = ""
                continue

            # Check if has GPS
            manifest = load_tracking_manifest(session_dir)
            if not manifest or not manifest.has_gps:
                row["center_lat"] = ""
                row["center_lng"] = ""
                continue

            # Get coordinates and calculate center
            coords = get_coordinates(session_dir)
            if coords:
                lats = [c[0] for c in coords]
                lngs = [c[1] for c in coords]
                row["center_lat"] = str(round((min(lats) + max(lats)) / 2, 6))
                row["center_lng"] = str(round((min(lngs) + max(lngs)) / 2, 6))
                updated_count += 1
            else:
                row["center_lat"] = ""
                row["center_lng"] = ""

        # Write updated sessions.tsv
        with open(sessions_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)

    return updated_count


def run_full_migration(
    data_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run all migrations on the data directory.

    1. Rename sub= directories to athl=
    2. Generate athletes.tsv
    3. Add center coords to sessions.tsv

    Args:
        data_dir: Base data directory.
        dry_run: If True, only report what would be done.

    Returns:
        Dictionary with migration results.
    """
    results: dict[str, Any] = {
        "prefix_renames": [],
        "athletes_tsv": None,
        "sessions_updated": 0,
    }

    # 1. Migrate prefixes
    if needs_migration(data_dir):
        renames = migrate_athlete_prefixes(data_dir, dry_run=dry_run)
        results["prefix_renames"] = [(str(old), str(new)) for old, new in renames]

    if not dry_run:
        # 2. Generate athletes.tsv
        athletes_path = generate_athletes_tsv(data_dir)
        results["athletes_tsv"] = str(athletes_path)

        # 3. Add center coords
        results["sessions_updated"] = add_center_coords_to_sessions(data_dir)

    return results
