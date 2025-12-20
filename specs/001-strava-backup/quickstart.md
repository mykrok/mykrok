# Quickstart: Strava Activity Backup

## Prerequisites

- Python 3.10+
- Strava account with activities
- Strava API application (free, see setup below)

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

## Strava API Setup

1. Go to https://www.strava.com/settings/api
2. Create a new application:
   - Application Name: "My Backup Tool"
   - Category: "Personal"
   - Website: "http://localhost"
   - Authorization Callback Domain: "localhost"
3. Note your **Client ID** and **Client Secret**

## First-Time Authentication

```bash
# Authenticate with Strava
strava-backup auth --client-id YOUR_ID --client-secret YOUR_SECRET

# Browser opens for OAuth authorization
# After approval, token is saved automatically
```

## Basic Usage

### Sync All Activities

```bash
# Initial full sync (may take a while for large histories)
strava-backup sync

# Incremental sync (daily usage)
strava-backup sync
```

### View Statistics

```bash
# Overall stats
strava-backup view stats

# Stats for 2025
strava-backup view stats --year 2025

# Monthly breakdown
strava-backup view stats --by-month
```

### Generate Map

```bash
# Create HTML map of all activities
strava-backup view map --output my-activities.html

# Create heatmap and serve locally
strava-backup view map --heatmap --serve
```

### Export to FitTrackee

```bash
# Export to FitTrackee instance
strava-backup export fittrackee \
  --url https://fittrackee.example.com \
  --email your@email.com

# Preview what would be exported
strava-backup export fittrackee --dry-run
```

### Browse Offline

```bash
# Start local browser
strava-backup browse

# Opens http://127.0.0.1:8080 with your activities
```

## Directory Structure After Sync

```
data/
└── athl=athlete123/
    ├── sessions.tsv              # Activity summary
    ├── gear.json                 # Your equipment
    └── ses=20251218T063000/      # Individual activity
        ├── info.json             # Metadata
        ├── tracking.parquet      # GPS + sensors
        ├── tracking.json         # Data manifest
        └── photos/
            └── 20251218T063500.jpg
```

## Query with DuckDB

```bash
# Start DuckDB CLI
duckdb

# Query your activities
.mode markdown
SELECT sport, SUM(distance_m)/1000 as km, COUNT(*) as activities
FROM read_csv_auto('data/athl=*/sessions.tsv')
GROUP BY sport;

# Query GPS tracks
SELECT ses, AVG(heartrate) as avg_hr, MAX(heartrate) as max_hr
FROM read_parquet('data/**/tracking.parquet', hive_partitioning=true)
WHERE heartrate > 0
GROUP BY ses;
```

## Cron Setup for Daily Backups

```bash
# Edit crontab
crontab -e

# Add daily sync at 2 AM
0 2 * * * cd /path/to/strava-backup && .venv/bin/strava-backup sync --quiet
```

## Configuration File

Create `~/.config/strava-backup/config.toml`:

```toml
[strava]
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"

[data]
directory = "/home/user/strava-backup/data"

[fittrackee]
url = "https://fittrackee.example.com"
email = "your@email.com"
```

## Troubleshooting

### Token Expired
```bash
# Re-authenticate
strava-backup auth --force
```

### Rate Limit Hit
The tool automatically pauses and resumes. For large initial syncs, run overnight.

### Missing GPS Data
Some activities (treadmill, manual entries) have no GPS. They appear in sessions.tsv but not on maps.

### Photo Download Failed
Photo URLs expire. Re-run sync to retry failed photos:
```bash
strava-backup sync --full
```
