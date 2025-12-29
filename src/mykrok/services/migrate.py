"""Migration utilities for MyKrok.

Handles data format migrations between versions.
"""

from __future__ import annotations

import contextlib
import csv
import re
import shutil
from pathlib import Path
from typing import Any

from mykrok.lib.paths import (
    ATHLETE_PREFIX,
    ATHLETE_PREFIX_LEGACY,
    get_athletes_tsv_path,
    get_sessions_tsv_path,
    iter_athlete_dirs,
    needs_migration,
)
from mykrok.models.tracking import get_coordinates, load_tracking_manifest


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
            username = entry.name[len(ATHLETE_PREFIX_LEGACY) :]
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
    from mykrok.models.athlete import load_athlete_profile

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

        rows.append(
            {
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
            }
        )

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


def update_annex_addunlocked(dataset_dir: Path, dry_run: bool = False) -> bool:
    """Update git-annex annex.addunlocked config from .strava-backup to .mykrok.

    The annex.addunlocked config controls which files are added in unlocked
    (regular file) mode. This needs to be updated BEFORE renaming the config
    directory so that the file remains unlocked after the move.

    Args:
        dataset_dir: Dataset root directory.
        dry_run: If True, only report what would be done.

    Returns:
        True if config was updated (or would be), False otherwise.
    """
    import subprocess

    try:
        # Check current annex.addunlocked config
        result = subprocess.run(
            ["git", "annex", "config", "--get", "annex.addunlocked"],
            cwd=str(dataset_dir),
            capture_output=True,
            text=True,
        )
        current_config = result.stdout.strip()

        # Check if it references .strava-backup
        if ".strava-backup" not in current_config:
            return False

        # Update to use .mykrok
        new_config = current_config.replace(".strava-backup", ".mykrok")

        if dry_run:
            return True

        subprocess.run(
            ["git", "annex", "config", "--set", "annex.addunlocked", new_config],
            cwd=str(dataset_dir),
            check=True,
            capture_output=True,
        )
        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        # git-annex not available or config not set
        return False


def migrate_config_directory(dataset_dir: Path, dry_run: bool = False) -> dict[str, Any]:
    """Migrate config directory from .strava-backup to .mykrok.

    Renames the legacy .strava-backup/ config directory to the new .mykrok/
    name. Also migrates the legacy .strava-backup.toml single-file config
    to .mykrok/config.toml if present.

    IMPORTANT: This function also updates the git-annex annex.addunlocked
    config BEFORE renaming, to ensure the config file remains unlocked.

    NOTE: If the config file shows as a pointer file after `git reset --hard`,
    `git annex unlock` may not restore the content. Use `git annex fsck` instead.
    See: https://git-annex.branchable.com/bugs/get_of_unlocked___34__absent__34___file_does_nothing_/

    Args:
        dataset_dir: Dataset root directory.
        dry_run: If True, only report what would be done.

    Returns:
        Dictionary with migration results:
            - dir_renamed: tuple of (old_path, new_path) if directory was renamed
            - file_migrated: tuple of (old_path, new_path) if file was migrated
            - annex_config_updated: True if annex.addunlocked was updated
    """
    results: dict[str, Any] = {
        "dir_renamed": None,
        "file_migrated": None,
        "annex_config_updated": False,
        "config_content_updated": False,
    }

    old_dir = dataset_dir / ".strava-backup"
    new_dir = dataset_dir / ".mykrok"
    legacy_file = dataset_dir / ".strava-backup.toml"

    # Migrate directory if it exists and new one doesn't
    if old_dir.exists() and old_dir.is_dir():
        if new_dir.exists():
            # New directory already exists - can't auto-migrate
            # User needs to manually merge
            pass
        else:
            # Update annex.addunlocked BEFORE renaming the directory
            # This ensures the config file stays unlocked after the move
            results["annex_config_updated"] = update_annex_addunlocked(
                dataset_dir, dry_run=dry_run
            )

            results["dir_renamed"] = (str(old_dir), str(new_dir))
            if not dry_run:
                shutil.move(str(old_dir), str(new_dir))

    # Migrate legacy single-file config if present
    if legacy_file.exists() and legacy_file.is_file():
        new_config_path = new_dir / "config.toml"
        if not new_config_path.exists():
            results["file_migrated"] = (str(legacy_file), str(new_config_path))
            if not dry_run:
                new_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(legacy_file), str(new_config_path))

    # Update config file contents to replace strava-backup references
    # In dry-run mode, check the old location; otherwise check the new location
    config_file = old_dir / "config.toml" if dry_run else new_dir / "config.toml"
    if config_file.exists():
        try:
            content = config_file.read_text(encoding="utf-8")
            if "strava-backup" in content:
                results["config_content_updated"] = True
                if not dry_run:
                    # Replace CLI command references in comments
                    new_content = content.replace("strava-backup", "mykrok")
                    (new_dir / "config.toml").write_text(new_content, encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # Skip if file can't be read (e.g., annex pointer)
            pass

    return results


def update_gitattributes_paths(dataset_dir: Path, dry_run: bool = False) -> bool:
    """Update .gitattributes to use new .mykrok path instead of .strava-backup.

    Replaces references to .strava-backup/config.toml with .mykrok/config.toml
    in the .gitattributes file.

    Args:
        dataset_dir: Dataset root directory containing .gitattributes.
        dry_run: If True, only report what would be done.

    Returns:
        True if file was updated (or would be updated), False otherwise.
    """
    gitattributes_path = dataset_dir / ".gitattributes"

    if not gitattributes_path.exists():
        return False

    content = gitattributes_path.read_text(encoding="utf-8")

    # Check if legacy paths are present
    if ".strava-backup" not in content:
        return False

    if dry_run:
        return True

    # Replace legacy paths with new paths
    new_content = re.sub(
        r"\.strava-backup(/config\.toml)?",
        r".mykrok\1",
        content,
    )

    if new_content != content:
        gitattributes_path.write_text(new_content, encoding="utf-8")
        return True

    return False


def update_dataset_template_files(dataset_dir: Path, dry_run: bool = False) -> list[str]:
    """Update README.md, Makefile, and .gitignore to use new mykrok naming.

    Replaces references to strava-backup with mykrok in dataset template files.

    Args:
        dataset_dir: Dataset root directory.
        dry_run: If True, only report what would be done.

    Returns:
        List of updated file names.
    """
    updated_files: list[str] = []

    # Define replacements for each file type
    # Order matters - more specific patterns first
    replacements = [
        # Config directory path
        (r"\.strava-backup/", ".mykrok/"),
        (r"\.strava-backup", ".mykrok"),
        # CLI commands - all subcommands
        (r"\bstrava-backup\b", "mykrok"),
        # Comments and headers
        (r"# Strava Backup\b", "# MyKrok Activity Backup"),
        (r"Strava Backup Makefile", "MyKrok Activity Backup Makefile"),
        (r"Strava Backup Commands", "MyKrok Commands"),
        (r"Strava Backup Dataset", "MyKrok Activity Backup Dataset"),
        # Commit messages in Makefile
        (r'"Sync new Strava activities"', '"Sync new activities"'),
        (r'"Full Strava sync"', '"Full activity sync"'),
        # GitHub URLs
        (r"github\.com/yourusername/strava-backup", "github.com/mykrok/mykrok"),
        (r"github\.com/[^/]+/strava-backup", "github.com/mykrok/mykrok"),
        # Directory cloning examples
        (r"my-strava-backup", "my-mykrok"),
        # Old CLI commands -> new commands (more specific first)
        (r"mykrok view map --serve", "mykrok create-browser --serve"),
        (r"mykrok view map --heatmap[^\n]*", "mykrok create-browser"),  # heatmap not supported
        (r"mykrok view map", "mykrok create-browser"),
        (r"mykrok browse", "mykrok create-browser --serve"),
        # Makefile target names (map: -> browser:, browse: -> browser:)
        (r"^map:", "browser:"),
        (r"^browse:", "browser:"),  # browse: becomes browser:
        (r"^heatmap:", "generate-browser:"),  # repurpose heatmap target
        # .PHONY line updates
        (r"\.PHONY:(.*)( map )(.*)$", r".PHONY:\1 browser \3"),
        (r"\.PHONY:(.*)( browse )(.*)$", r".PHONY:\1 browser \3"),
        (r"\.PHONY:(.*)( heatmap )(.*)$", r".PHONY:\1 generate-browser \3"),
        # Help text updates
        (r"View activities on map", "Generate and serve interactive browser"),
        (r"Generate heatmap HTML", "Generate browser (without serving)"),
        (r"Start offline browser", "Generate and serve interactive browser"),
        (r"make map\s+- ", "make browser       - "),
        (r"make heatmap\s+- ", "make generate-browser - "),
        (r"make browse\s+- ", "make browser       - "),
    ]

    for filename in ["README.md", "Makefile", ".gitignore"]:
        filepath = dataset_dir / filename
        if not filepath.exists():
            continue

        content = filepath.read_text(encoding="utf-8")
        original_content = content

        # Check if any replacements are needed
        needs_update = False
        for pattern, _ in replacements:
            if re.search(pattern, content, re.MULTILINE):
                needs_update = True
                break

        if not needs_update:
            continue

        if dry_run:
            updated_files.append(filename)
            continue

        # Apply all replacements (MULTILINE for ^ patterns in Makefile)
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        if content != original_content:
            filepath.write_text(content, encoding="utf-8")
            updated_files.append(filename)

    return updated_files


def run_full_migration(
    data_dir: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run all migrations on the data directory.

    1. Migrate config directory from .strava-backup to .mykrok
    2. Update .gitattributes to use new .mykrok path
    3. Update README.md, Makefile, .gitignore to use mykrok naming
    4. Rename sub= directories to athl=
    5. Update Makefile and README.md to use athl= prefix
    6. Add .gitattributes rule for log files (route to git-annex)
    7. Migrate center_lat/center_lng columns to start_lat/start_lng
    8. Generate athletes.tsv

    Note: start_lat/start_lng columns are now included by default when
    sessions.tsv is regenerated via update_sessions_tsv().

    Args:
        data_dir: Base data directory.
        dry_run: If True, only report what would be done.

    Returns:
        Dictionary with migration results.
    """
    results: dict[str, Any] = {
        "config_dir_migrated": None,
        "config_file_migrated": None,
        "annex_config_updated": False,
        "config_content_updated": False,
        "gitattributes_paths_updated": False,
        "template_files_updated": [],
        "prefix_renames": [],
        "dataset_files_updated": [],
        "log_gitattributes_added": False,
        "coords_columns_migrated": 0,
        "athletes_tsv": None,
    }

    # Determine dataset root directory
    # The config directory (.strava-backup/ or .mykrok/) is typically in:
    # 1. The current working directory (where user runs the command from)
    # 2. The data directory itself
    # 3. The parent of the data directory (if data/ subdirectory is used)
    #
    # IMPORTANT: cwd must be checked FIRST because when config has
    # `directory = ".."`, data_dir resolves to the PARENT of the dataset root,
    # but the user runs the command from the dataset root itself.
    cwd = Path.cwd()
    data_dir_resolved = data_dir.resolve()

    # Check possible locations for dataset root (where config dir lives)
    # Order matters: prioritize cwd since user runs command from dataset root
    possible_roots = [cwd, data_dir_resolved, data_dir_resolved.parent]

    # Find the dataset root by looking for config directory
    # FIRST pass: look for .strava-backup or .mykrok (config directories)
    # These take priority over .datalad because the migration is about
    # renaming the config directory
    dataset_dir = cwd  # default to cwd, where user runs the command
    found_config_dir = False
    for candidate in possible_roots:
        if (candidate / ".strava-backup").exists() or (candidate / ".mykrok").exists():
            dataset_dir = candidate
            found_config_dir = True
            break

    # SECOND pass: if no config dir found, fall back to .datalad
    if not found_config_dir:
        for candidate in possible_roots:
            if (candidate / ".datalad").exists():
                dataset_dir = candidate
                break

    # 1. Migrate config directory from .strava-backup to .mykrok
    # This also updates annex.addunlocked config BEFORE renaming
    config_results = migrate_config_directory(dataset_dir, dry_run=dry_run)
    results["config_dir_migrated"] = config_results.get("dir_renamed")
    results["config_file_migrated"] = config_results.get("file_migrated")
    results["annex_config_updated"] = config_results.get("annex_config_updated", False)
    results["config_content_updated"] = config_results.get("config_content_updated", False)

    # 2. Update .gitattributes to use new .mykrok path
    results["gitattributes_paths_updated"] = update_gitattributes_paths(
        dataset_dir, dry_run=dry_run
    )

    # 3. Update README.md, Makefile, .gitignore to use mykrok naming
    results["template_files_updated"] = update_dataset_template_files(
        dataset_dir, dry_run=dry_run
    )

    # 4. Migrate prefixes
    if needs_migration(data_dir):
        renames = migrate_athlete_prefixes(data_dir, dry_run=dry_run)
        results["prefix_renames"] = [(str(old), str(new)) for old, new in renames]

    # 5. Update Makefile and README.md in dataset root (sub= -> athl=)
    results["dataset_files_updated"] = update_dataset_files(dataset_dir, dry_run=dry_run)

    # 6. Add log file gitattributes rule
    results["log_gitattributes_added"] = add_log_gitattributes_rule(dataset_dir, dry_run=dry_run)

    if not dry_run:
        # 7. Migrate center_* columns to start_* columns
        results["coords_columns_migrated"] = migrate_center_to_start_coords(data_dir)

        # 8. Generate athletes.tsv
        athletes_path = generate_athletes_tsv(data_dir)
        results["athletes_tsv"] = str(athletes_path)

    return results
