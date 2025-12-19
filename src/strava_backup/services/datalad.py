"""DataLad dataset creation service for strava-backup.

Creates a DataLad dataset configured for version-controlled Strava backups
with reproducible sync operations using `datalad run`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import datalad.api as dl


# Template for .strava-backup.toml config file with comments
CONFIG_TEMPLATE = """\
# Strava Backup Configuration
# ===========================
# This file contains the configuration for strava-backup.
# Fill in your Strava API credentials below.

[strava]
# Get your Client ID and Client Secret from:
# https://www.strava.com/settings/api
#
# Create an application with:
#   - Application Name: "My Backup Tool" (or any name)
#   - Category: "Personal"
#   - Website: "http://localhost"
#   - Authorization Callback Domain: "localhost"

client_id = ""      # Your Strava API Client ID (required)
client_secret = ""  # Your Strava API Client Secret (required)

# These fields are auto-populated after running: strava-backup auth
# access_token = ""
# refresh_token = ""
# token_expires_at = 0

[data]
# Directory where activity data will be stored (relative to this file)
directory = "./data"

[sync]
# What to download during sync
photos = true    # Download activity photos
streams = true   # Download GPS/sensor data (Parquet format)
comments = true  # Download comments and kudos

# Optional: FitTrackee export configuration
# [fittrackee]
# url = "https://fittrackee.example.com"
# email = "your@email.com"
# password can be set via FITTRACKEE_PASSWORD environment variable
"""

# Template for README.md in the dataset
README_TEMPLATE = """\
# Strava Activity Backup Dataset

This is a [DataLad](https://www.datalad.org/) dataset for backing up Strava activities
using [strava-backup](https://github.com/yourusername/strava-backup).

## Prerequisites

- Python 3.10+
- DataLad installed (`pip install datalad`)
- strava-backup installed (`pip install strava-backup`)

## Setup

1. Edit `.strava-backup.toml` with your Strava API credentials:
   - Get credentials from https://www.strava.com/settings/api
   - Fill in `client_id` and `client_secret`

2. Authenticate with Strava:
   ```bash
   strava-backup auth
   ```

3. Run initial sync:
   ```bash
   make sync
   ```

## Usage

### Sync New Activities

```bash
make sync
```

This uses `datalad run` to execute the sync command, automatically tracking:
- Which command was run
- Input/output files
- Creating a git commit with full provenance

### View Statistics

```bash
strava-backup view stats
strava-backup view stats --year 2025 --by-month
```

### Generate Map

```bash
strava-backup view map --serve
strava-backup view map --heatmap --output heatmap.html
```

### Browse Offline

```bash
strava-backup browse
```

## Directory Structure

```
./
├── .strava-backup.toml    # Configuration (credentials)
├── Makefile               # Automation commands
├── README.md              # This file
└── data/                  # Backed-up activities
    └── sub={username}/
        ├── sessions.tsv
        ├── gear.json
        └── ses={datetime}/
            ├── info.json
            ├── tracking.parquet
            └── photos/
```

## Reproducibility

All sync operations are recorded using `datalad run`, which means:

- Every sync creates a commit with the exact command used
- You can see what changed between syncs
- You can reproduce any historical state
- Binary files (photos, parquet) are handled efficiently by git-annex

### View History

```bash
git log --oneline
datalad diff --from HEAD~1
```

### Get Dataset on Another Machine

```bash
datalad clone <url-or-path> my-strava-backup
cd my-strava-backup
datalad get data/  # Download all data files
```

## Data Safety

- Text files (JSON, TSV) are tracked directly in git
- Binary files (photos, Parquet) are tracked by git-annex
- **`.strava-backup.toml` is tracked by git-annex** (not plain git) because it
  contains OAuth tokens after authentication
- The config file has git-annex metadata `distribution-restrictions=sensitive`

**Important**: Consider keeping this dataset private if it contains your
actual Strava data, as it may include personal location information.
"""

# Template for Makefile
MAKEFILE_TEMPLATE = """\
# Strava Backup Makefile
# ======================
# Uses datalad run for reproducible, version-controlled backups

.PHONY: sync sync-full auth stats map browse help

# Default target
all: sync

# Incremental sync - only fetch new activities
sync:
	datalad run -m "Sync new Strava activities" \\
		-o "data/" \\
		"strava-backup sync"

# Full sync - re-download everything
sync-full:
	datalad run -m "Full Strava sync" \\
		-o "data/" \\
		"strava-backup sync --full"

# Authenticate with Strava (interactive)
auth:
	strava-backup auth

# View statistics
stats:
	strava-backup view stats

# View statistics by month
stats-monthly:
	strava-backup view stats --by-month --by-type

# Generate and serve map
map:
	strava-backup view map --serve

# Generate heatmap
heatmap:
	strava-backup view map --heatmap --output heatmap.html

# Start offline browser
browse:
	strava-backup browse

# Show help
help:
	@echo "Strava Backup Commands:"
	@echo "  make sync        - Sync new activities (incremental)"
	@echo "  make sync-full   - Re-sync all activities"
	@echo "  make auth        - Authenticate with Strava"
	@echo "  make stats       - Show activity statistics"
	@echo "  make map         - View activities on map"
	@echo "  make heatmap     - Generate heatmap HTML"
	@echo "  make browse      - Start offline browser"
"""

# Template for .gitignore additions
GITIGNORE_TEMPLATE = """\
# Strava Backup
# Note: .strava-backup.toml is tracked by git-annex (not git) for security
# It contains OAuth tokens after authentication

# Temporary files
*.pyc
__pycache__/
.DS_Store

# Generated files that shouldn't be tracked
*.html
!README.html
"""

# Template for .gitattributes - forces config file to git-annex
GITATTRIBUTES_TEMPLATE = """\
# Force .strava-backup.toml to be tracked by git-annex (contains sensitive tokens)
# This ensures credentials are not stored in plain git history
.strava-backup.toml annex.largefiles=anything
"""


def create_datalad_dataset(
    path: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Create a DataLad dataset configured for Strava backups.

    Creates a new DataLad dataset with the text2git configuration
    (text files in git, binary files in git-annex) and populates it
    with configuration templates.

    Args:
        path: Path where the dataset should be created.
        force: If True, overwrite existing files.

    Returns:
        Dictionary with creation results.

    Raises:
        FileExistsError: If path exists and is not empty (unless force=True).
        RuntimeError: If dataset creation fails.
    """
    path = Path(path).resolve()

    # Check if path exists and is not empty
    if path.exists() and any(path.iterdir()) and not force:
        raise FileExistsError(
            f"Directory {path} exists and is not empty. Use force=True to overwrite."
        )

    # Create the dataset with text2git configuration
    try:
        dataset = dl.create(
            path=str(path),
            cfg_proc="text2git",
            force=force,
        )
    except Exception as e:
        raise RuntimeError(f"Failed to create DataLad dataset: {e}") from e

    # Create template files
    config_path = path / ".strava-backup.toml"
    readme_path = path / "README.md"
    makefile_path = path / "Makefile"
    gitignore_path = path / ".gitignore"
    gitattributes_path = path / ".gitattributes"
    data_dir = path / "data"

    # Write .gitattributes FIRST to ensure config file goes to git-annex
    # This must be committed before the config file is added
    existing_gitattributes = gitattributes_path.read_text() if gitattributes_path.exists() else ""
    gitattributes_path.write_text(existing_gitattributes + "\n" + GITATTRIBUTES_TEMPLATE)

    # Commit .gitattributes first so the rules are in effect
    try:
        dataset.save(
            path=[str(gitattributes_path)],
            message="Configure git-annex to track sensitive config file",
        )
    except Exception as e:
        raise RuntimeError(f"Failed to save .gitattributes: {e}") from e

    # Write config template (will now be tracked by git-annex due to .gitattributes)
    config_path.write_text(CONFIG_TEMPLATE)

    # Write README
    readme_path.write_text(README_TEMPLATE)

    # Write Makefile
    makefile_path.write_text(MAKEFILE_TEMPLATE)

    # Append to .gitignore (DataLad creates one)
    existing_gitignore = gitignore_path.read_text() if gitignore_path.exists() else ""
    gitignore_path.write_text(existing_gitignore + "\n" + GITIGNORE_TEMPLATE)

    # Create data directory
    data_dir.mkdir(exist_ok=True)
    (data_dir / ".gitkeep").touch()

    # Save the files to the dataset
    # We use the dataset object directly to avoid confusion with parent datasets
    try:
        dataset.save(
            message="Initialize strava-backup dataset with templates",
        )
    except Exception as e:
        raise RuntimeError(f"Failed to save dataset: {e}") from e

    # Add git-annex metadata to mark config file as sensitive
    # This helps tools understand this file contains private data
    try:
        subprocess.run(
            [
                "git", "annex", "metadata",
                "-s", "distribution-restrictions=sensitive",
                ".strava-backup.toml",
            ],
            cwd=str(path),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        # Metadata setting is best-effort; don't fail if it doesn't work
        pass
    except FileNotFoundError:
        # git-annex not available; skip metadata
        pass

    return {
        "path": str(path),
        "config_file": str(config_path),
        "readme_file": str(readme_path),
        "makefile": str(makefile_path),
        "data_dir": str(data_dir),
        "status": "created",
    }
