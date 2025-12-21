"""Migration utilities for strava-backup.

Handles data format migrations between versions.
"""

from __future__ import annotations

import contextlib
import csv
from pathlib import Path
from typing import Any

from strava_backup.lib.paths import (
    ATHLETE_PREFIX,
    ATHLETE_PREFIX_LEGACY,
    get_athletes_tsv_path,
    get_sessions_tsv_path,
    iter_athlete_dirs,
    needs_migration,
)
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
        username, firstname, lastname, city, country, session_count, first_activity,
        last_activity, total_distance_km, total_moving_time_h, activity_types

    Args:
        data_dir: Base data directory.

    Returns:
        Path to generated athletes.tsv.
    """
    from strava_backup.models.athlete import load_athlete_profile

    athletes_path = get_athletes_tsv_path(data_dir)

    rows: list[dict[str, Any]] = []

    for username, athlete_dir in iter_athlete_dirs(data_dir):
        sessions_path = get_sessions_tsv_path(athlete_dir)

        # Load athlete profile if available
        athlete = load_athlete_profile(athlete_dir)

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
                    with contextlib.suppress(ValueError):
                        total_distance_m += float(row.get("distance_m", 0) or 0)

                    with contextlib.suppress(ValueError):
                        total_moving_time_s += int(row.get("moving_time_s", 0) or 0)

                    # Collect activity types
                    sport = row.get("sport", "")
                    if sport:
                        activity_types.add(sport)

        rows.append({
            "username": username,
            "firstname": athlete.firstname if athlete else "",
            "lastname": athlete.lastname if athlete else "",
            "city": athlete.city if athlete else "",
            "country": athlete.country if athlete else "",
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
        "firstname",
        "lastname",
        "city",
        "country",
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


def add_center_coords_to_sessions(data_dir: Path, force: bool = False) -> int:
    """Add start point GPS coordinates to sessions.tsv files.

    Adds center_lat and center_lng columns using the track's starting point.
    Column names kept as center_* for backward compatibility.

    Args:
        data_dir: Base data directory.
        force: If True, recalculate even if columns already exist.

    Returns:
        Number of sessions updated.
    """
    updated_count = 0

    for _username, athlete_dir in iter_athlete_dirs(data_dir):
        sessions_path = get_sessions_tsv_path(athlete_dir)
        if not sessions_path.exists():
            continue

        # Read existing sessions
        with open(sessions_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        # Check if center coords already exist
        has_columns = "center_lat" in fieldnames and "center_lng" in fieldnames
        if has_columns and not force:
            continue

        # Add new columns if not present
        if "center_lat" not in fieldnames:
            fieldnames.append("center_lat")
        if "center_lng" not in fieldnames:
            fieldnames.append("center_lng")

        # Get starting point coords for each session
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

            # Get coordinates and use starting point (first coordinate)
            coords = get_coordinates(session_dir)
            if coords:
                start_lat, start_lng = coords[0]
                row["center_lat"] = str(round(start_lat, 6))
                row["center_lng"] = str(round(start_lng, 6))
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


def update_dataset_files(dataset_dir: Path, dry_run: bool = False) -> list[str]:
    """Update Makefile and README.md to use athl= prefix instead of sub=.

    Args:
        dataset_dir: Dataset root directory (parent of data directory).
        dry_run: If True, only report what would be done.

    Returns:
        List of updated file paths.
    """
    updated_files: list[str] = []

    for filename in ["Makefile", "README.md"]:
        filepath = dataset_dir / filename
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")
        if "sub=" not in content:
            continue

        if not dry_run:
            new_content = content.replace("sub=", "athl=")
            filepath.write_text(new_content, encoding="utf-8")

        updated_files.append(str(filepath))

    return updated_files


# Gitattributes rule for log files (to avoid bloating .git/objects)
LOG_GITATTRIBUTES_RULE = """\
# Force log files to git-annex to avoid bloating .git/objects
*.log annex.largefiles=anything
logs/**/*.log annex.largefiles=anything
"""


def add_log_gitattributes_rule(dataset_dir: Path, dry_run: bool = False) -> bool:
    """Add gitattributes rule to force log files to git-annex.

    This prevents log files from bloating .git/objects by routing them
    to git-annex instead.

    Args:
        dataset_dir: Dataset root directory containing .gitattributes.
        dry_run: If True, only report what would be done.

    Returns:
        True if rule was added (or would be added), False if already present.
    """
    gitattributes_path = dataset_dir / ".gitattributes"

    # Check if .gitattributes exists and already has the rule
    if gitattributes_path.exists():
        content = gitattributes_path.read_text(encoding="utf-8")
        # Check if the essential rule is already present
        if "*.log annex.largefiles" in content:
            return False
    else:
        content = ""

    if dry_run:
        return True

    # Append the rule
    new_content = content.rstrip() + "\n\n" + LOG_GITATTRIBUTES_RULE
    gitattributes_path.write_text(new_content, encoding="utf-8")
    return True


def run_full_migration(
    data_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run all migrations on the data directory.

    1. Rename sub= directories to athl=
    2. Update Makefile and README.md to use athl=
    3. Add .gitattributes rule for log files (route to git-annex)
    4. Generate athletes.tsv
    5. Add center coords to sessions.tsv

    Args:
        data_dir: Base data directory.
        dry_run: If True, only report what would be done.

    Returns:
        Dictionary with migration results.
    """
    results: dict[str, Any] = {
        "prefix_renames": [],
        "dataset_files_updated": [],
        "log_gitattributes_added": False,
        "athletes_tsv": None,
        "sessions_updated": 0,
    }

    # 1. Migrate prefixes
    if needs_migration(data_dir):
        renames = migrate_athlete_prefixes(data_dir, dry_run=dry_run)
        results["prefix_renames"] = [(str(old), str(new)) for old, new in renames]

    # 2. Update Makefile and README.md in dataset root
    # The dataset root is typically the parent of the data directory,
    # or the data directory itself if it's the dataset root
    dataset_dir = data_dir.parent if (data_dir.parent / ".datalad").exists() else data_dir
    # Also check if data_dir itself is the dataset root
    if not (dataset_dir / ".datalad").exists() and (data_dir / ".datalad").exists():
        dataset_dir = data_dir
    results["dataset_files_updated"] = update_dataset_files(dataset_dir, dry_run=dry_run)

    # 3. Add log file gitattributes rule
    results["log_gitattributes_added"] = add_log_gitattributes_rule(dataset_dir, dry_run=dry_run)

    if not dry_run:
        # 4. Generate athletes.tsv
        athletes_path = generate_athletes_tsv(data_dir)
        results["athletes_tsv"] = str(athletes_path)

        # 5. Add center coords
        results["sessions_updated"] = add_center_coords_to_sessions(data_dir)

    return results
