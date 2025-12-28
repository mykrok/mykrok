"""DataLad dataset creation service for MyKrok.

Creates a DataLad dataset configured for version-controlled activity backups
with reproducible sync operations using `datalad run`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import datalad.api as dl

# Template for .mykrok/config.toml config file with comments
CONFIG_TEMPLATE = """\
# MyKrok Configuration
# ===========================
# This file contains the configuration for MyKrok.
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

# NOTE: OAuth tokens are stored separately in oauth-tokens.toml (gitignored)
# They are auto-populated after running: mykrok auth

[data]
# Directory where activity data will be stored (relative to dataset root)
# Data is stored in Hive-partitioned structure: athl={username}/ses={datetime}/
directory = ".."

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

# Template for .gitignore in .mykrok/ directory
CONFIG_GITIGNORE_TEMPLATE = """\
# OAuth tokens - do not commit to version control
oauth-tokens.toml
"""

# Template for README.md in the dataset
README_TEMPLATE = """\
# MyKrok Activity Backup Dataset

This is a [DataLad](https://www.datalad.org/) dataset for backing up fitness activities
using [MyKrok](https://github.com/mykrok/mykrok). Currently supports Strava as the data source.

## Prerequisites

- Python 3.10+
- DataLad installed (`pip install datalad`)
- mykrok installed (`pip install mykrok`)

## Setup

1. Edit `.mykrok/config.toml` with your Strava API credentials:
   - Get credentials from https://www.strava.com/settings/api
   - Fill in `client_id` and `client_secret`

2. Authenticate with Strava:
   ```bash
   mykrok auth
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
mykrok view stats
mykrok view stats --year 2025 --by-month
```

### View Data Files

[visidata](https://www.visidata.org/) is recommended for exploring Parquet and TSV files:

```bash
pip install visidata pyarrow
vd athl=*/sessions.tsv                    # View all sessions
vd athl=*/ses=*/tracking.parquet          # View GPS/sensor data
```

### Generate Interactive Browser

```bash
mykrok create-browser --serve
```

The browser includes:
- Interactive map with activity markers and GPS tracks
- Sessions list with filtering by date, type, and search
- Statistics dashboard with charts
- Heatmap layer toggle
- Photo viewing
- Offline support (works without internet)

## Directory Structure

```
./
├── .mykrok/        # Configuration directory
│   ├── config.toml        # Strava API credentials
│   └── oauth-tokens.toml  # OAuth tokens (gitignored)
├── Makefile               # Automation commands
├── README.md              # This file
└── athl={username}/       # Backed-up activities (Hive-partitioned)
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
datalad clone <url-or-path> my-mykrok-backup
cd my-mykrok-backup
datalad get data/  # Download all data files
```

## Data Safety

- Text files (JSON, TSV) are tracked directly in git
- Binary files (photos, Parquet) are tracked by git-annex
- **`.mykrok/config.toml` is tracked by git-annex** (not plain git) for security
- The config file has git-annex metadata `distribution-restrictions=sensitive`
- OAuth tokens in `.mykrok/oauth-tokens.toml` are gitignored (never committed)

**Important**: Consider keeping this dataset private if it contains your
actual Strava data, as it may include personal location information.

## Publishing to a Web Server

You can publish the dataset to a remote HTTP server via SSH for viewing in a browser.

### Setup a Publishing Remote

```bash
# Create a sibling that excludes sensitive files
datalad create-sibling -s public-website \\
    --annex-wanted "not metadata=distribution-restrictions=*" \\
    SSH_URL

# Example: datalad create-sibling -s public-website \\
#     --annex-wanted "not metadata=distribution-restrictions=*" \\
#     user@server.example.com:/var/www/mykrok
```

### Publish Updates

```bash
datalad push --to=public-website
```

This publishes the dataset while automatically excluding files marked as sensitive
(like `.mykrok/config.toml`).

### Access Control

**Note**: Access restrictions and user management are outside the scope of this
project. Implement access control using your web server's authentication
mechanisms (e.g., HTTP Basic Auth, OAuth proxy, IP allowlisting, etc.).
"""

# Template for Makefile
MAKEFILE_TEMPLATE = """\
# MyKrok Activity Backup Makefile
# ================================
# Uses datalad run for reproducible, version-controlled backups

.PHONY: sync sync-full auth stats browser generate-browser help

# Default target
all: sync

# Incremental sync - only fetch new activities
sync:
	datalad run -m "Sync new activities" \\
		-o "athl=*" \\
		"mykrok sync"

# Full sync - re-download everything
sync-full:
	datalad run -m "Full activity sync" \\
		-o "athl=*" \\
		"mykrok sync --full"

# Authenticate with data source (interactive)
auth:
	mykrok auth

# View statistics
stats:
	mykrok view stats

# View statistics by month
stats-monthly:
	mykrok view stats --by-month --by-type

# Generate and serve interactive browser
browser:
	mykrok create-browser --serve

# Generate interactive browser (without serving)
generate-browser:
	mykrok create-browser

# Show help
help:
	@echo "MyKrok Activity Backup Commands:"
	@echo "  make sync            - Sync new activities (incremental)"
	@echo "  make sync-full       - Re-sync all activities"
	@echo "  make auth            - Authenticate with data source"
	@echo "  make stats           - Show activity statistics"
	@echo "  make browser         - Generate and serve interactive browser"
	@echo "  make generate-browser - Generate browser (without serving)"
"""

# Template for .gitignore additions
GITIGNORE_TEMPLATE = """\
# MyKrok Activity Backup
# Note: .mykrok/config.toml is tracked by git-annex (not git) for security
# OAuth tokens in .mykrok/oauth-tokens.toml are gitignored (see .mykrok/.gitignore)

# Temporary files
*.pyc
__pycache__/
.DS_Store

# Generated files that shouldn't be tracked
*.html
!README.html
"""

# Template for .gitattributes - forces certain files to git-annex
GITATTRIBUTES_TEMPLATE = """\
# Force .mykrok/config.toml to be tracked by git-annex (contains sensitive data)
# This ensures API credentials are not stored in plain git history
.mykrok/config.toml annex.largefiles=anything

# Force log files to git-annex to avoid bloating .git/objects
*.log annex.largefiles=anything
logs/**/*.log annex.largefiles=anything
"""


def create_datalad_dataset(
    path: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Create a DataLad dataset configured for activity backups.

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

    # Create paths for template files
    config_dir = path / ".mykrok"
    config_path = config_dir / "config.toml"
    config_gitignore_path = config_dir / ".gitignore"
    readme_path = path / "README.md"
    makefile_path = path / "Makefile"
    gitignore_path = path / ".gitignore"
    gitattributes_path = path / ".gitattributes"

    # Create .mykrok directory
    config_dir.mkdir(parents=True, exist_ok=True)

    # Write .gitattributes FIRST to ensure config file goes to git-annex
    # This must be committed before the config file is added
    existing_gitattributes = (
        gitattributes_path.read_text(encoding="utf-8") if gitattributes_path.exists() else ""
    )
    gitattributes_path.write_text(
        existing_gitattributes + "\n" + GITATTRIBUTES_TEMPLATE, encoding="utf-8"
    )

    # Commit .gitattributes first so the rules are in effect
    try:
        dataset.save(
            path=[str(gitattributes_path)],
            message="Configure git-annex to track sensitive config file",
        )
    except Exception as e:
        raise RuntimeError(f"Failed to save .gitattributes: {e}") from e

    # Configure git-annex to add the config file unlocked (regular file, not symlink)
    # This makes it easier to edit the config file directly
    try:
        subprocess.run(
            [
                "git",
                "annex",
                "config",
                "--set",
                "annex.addunlocked",
                "include=.mykrok/config.toml",
            ],
            cwd=str(path),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        # Config setting is best-effort; don't fail if it doesn't work
        pass
    except FileNotFoundError:
        # git-annex not available; skip
        pass

    # Write config template (will now be tracked by git-annex due to .gitattributes)
    # The file will be added unlocked due to annex.addunlocked config
    config_path.write_text(CONFIG_TEMPLATE, encoding="utf-8")

    # Write .gitignore inside .mykrok/ to exclude oauth-tokens.toml
    config_gitignore_path.write_text(CONFIG_GITIGNORE_TEMPLATE, encoding="utf-8")

    # Write README
    readme_path.write_text(README_TEMPLATE, encoding="utf-8")

    # Write Makefile
    makefile_path.write_text(MAKEFILE_TEMPLATE, encoding="utf-8")

    # Append to .gitignore (DataLad creates one)
    existing_gitignore = (
        gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
    )
    gitignore_path.write_text(existing_gitignore + "\n" + GITIGNORE_TEMPLATE, encoding="utf-8")

    # Save the files to the dataset
    # We use the dataset object directly to avoid confusion with parent datasets
    try:
        dataset.save(
            message="Initialize mykrok dataset with templates",
        )
    except Exception as e:
        raise RuntimeError(f"Failed to save dataset: {e}") from e

    # Add git-annex metadata to mark config file as sensitive
    # This helps tools understand this file contains private data
    try:
        subprocess.run(
            [
                "git",
                "annex",
                "metadata",
                "-s",
                "distribution-restrictions=sensitive",
                ".mykrok/config.toml",
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
        "status": "created",
    }
