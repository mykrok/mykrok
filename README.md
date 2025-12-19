# strava-backup

CLI tool to backup Strava activities with incremental sync, map visualization, and FitTrackee export.

## Features

- **Backup Activities**: Download all your Strava activities including metadata, GPS tracks, photos, comments, and kudos
- **Incremental Sync**: Only fetch new activities after initial backup
- **Interactive Maps**: Generate HTML maps with route visualization and heatmap mode
- **Statistics**: View activity statistics by time period with breakdowns by type
- **Offline Browsing**: Browse your backed-up activities locally without internet
- **FitTrackee Export**: Export activities to self-hosted FitTrackee instances

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/strava-backup
cd strava-backup

# Install with uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[devel]"

# Or with pip
pip install -e ".[devel]"
```

## Quick Start

1. Create a Strava API application at https://www.strava.com/settings/api
2. Authenticate:
   ```bash
   strava-backup auth --client-id YOUR_ID --client-secret YOUR_SECRET
   ```
3. Sync activities:
   ```bash
   strava-backup sync
   ```
4. View your data:
   ```bash
   strava-backup view stats
   strava-backup view map --serve
   strava-backup browse
   ```

## Commands

- `strava-backup auth` - Authenticate with Strava
- `strava-backup sync` - Download activities from Strava
- `strava-backup gpx` - Export activities as GPX files
- `strava-backup view stats` - Show activity statistics
- `strava-backup view map` - Generate interactive map
- `strava-backup browse` - Start local activity browser
- `strava-backup export fittrackee` - Export to FitTrackee

## Data Storage

Activities are stored in a Hive-partitioned directory structure:

```
data/
└── sub={username}/
    ├── sessions.tsv
    ├── gear.json
    └── ses={datetime}/
        ├── info.json
        ├── tracking.parquet
        └── photos/
```

## License

MIT
