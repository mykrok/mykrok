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


def migrate_center_to_start_coords(data_dir: Path) -> int:
    """Migrate center_lat/center_lng columns to start_lat/start_lng.

    Renames the legacy center_* columns to start_* and computes any
    missing coordinate values from the track data.

    Args:
        data_dir: Base data directory.

    Returns:
        Number of files migrated.
    """
    migrated_count = 0

    for _username, athlete_dir in iter_athlete_dirs(data_dir):
        sessions_path = get_sessions_tsv_path(athlete_dir)
        if not sessions_path.exists():
            continue

        # Read existing sessions
        with open(sessions_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        # Check if migration is needed
        has_old = "center_lat" in fieldnames or "center_lng" in fieldnames
        has_new = "start_lat" in fieldnames and "start_lng" in fieldnames

        if has_new and not has_old:
            # Already migrated, nothing to do
            continue

        modified = False

        # Rename columns in fieldnames if old columns exist
        if has_old:
            new_fieldnames = []
            for col in fieldnames:
                if col == "center_lat":
                    new_fieldnames.append("start_lat")
                    modified = True
                elif col == "center_lng":
                    new_fieldnames.append("start_lng")
                    modified = True
                else:
                    new_fieldnames.append(col)
            fieldnames = new_fieldnames

            # Rename keys in rows and compute missing values
            for row in rows:
                if "center_lat" in row:
                    row["start_lat"] = row.pop("center_lat")
                if "center_lng" in row:
                    row["start_lng"] = row.pop("center_lng")

                # Compute missing values from track data
                session_key = row.get("datetime", "")
                if session_key and (not row.get("start_lat") or not row.get("start_lng")):
                    session_dir = athlete_dir / f"ses={session_key}"
                    if session_dir.exists():
                        manifest = load_tracking_manifest(session_dir)
                        if manifest and manifest.has_gps:
                            coords = get_coordinates(session_dir)
                            if coords:
                                start_lat, start_lng = coords[0]
                                row["start_lat"] = str(round(start_lat, 6))
                                row["start_lng"] = str(round(start_lng, 6))

        if modified:
            # Write updated sessions.tsv
            with open(sessions_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
                writer.writeheader()
                writer.writerows(rows)

            migrated_count += 1

    return migrated_count


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
    4. Migrate center_lat/center_lng columns to start_lat/start_lng
    5. Generate athletes.tsv

    Note: start_lat/start_lng columns are now included by default when
    sessions.tsv is regenerated via update_sessions_tsv().

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
        "coords_columns_migrated": 0,
        "athletes_tsv": None,
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
        # 4. Migrate center_* columns to start_* columns
        results["coords_columns_migrated"] = migrate_center_to_start_coords(data_dir)

        # 5. Generate athletes.tsv
        athletes_path = generate_athletes_tsv(data_dir)
        results["athletes_tsv"] = str(athletes_path)

    return results
