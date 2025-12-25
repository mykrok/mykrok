# Quickstart: Strava Activity Backup

## Prerequisites

- Python 3.10+
- Strava account with activities
- Strava API application (free, see setup below)

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/mykrok
cd mykrok

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
mykrok auth --client-id YOUR_ID --client-secret YOUR_SECRET

# Browser opens for OAuth authorization
# After approval, token is saved automatically
```

## Basic Usage

### Sync All Activities

```bash
# Initial full sync (may take a while for large histories)
mykrok sync

# Incremental sync (daily usage)
mykrok sync
```

### View Statistics

```bash
# Overall stats
mykrok view stats

# Stats for 2025
mykrok view stats --year 2025

# Monthly breakdown
mykrok view stats --by-month
```

### Generate Interactive Browser

```bash
# Generate HTML browser (writes mykrok.html to data directory)
mykrok create-browser

# Generate and serve locally
mykrok create-browser --serve

# Serve on custom port
mykrok create-browser --serve --port 9000
```

### Export to FitTrackee

```bash
# Export to FitTrackee instance
mykrok export fittrackee \
  --url https://fittrackee.example.com \
  --email your@email.com

# Preview what would be exported
mykrok export fittrackee --dry-run
```

### Browse Offline

```bash
# Generate browser and start local server
mykrok create-browser --serve

# Opens http://127.0.0.1:8080 with your activities
# The generated mykrok.html works offline - just open it directly
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
0 2 * * * cd /path/to/mykrok && .venv/bin/mykrok sync --quiet
```

## Configuration File

Create `~/.config/mykrok/config.toml`:

```toml
[strava]
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"

[data]
directory = "/home/user/mykrok/data"

[fittrackee]
url = "https://fittrackee.example.com"
email = "your@email.com"
```

## Troubleshooting

### Token Expired
```bash
# Re-authenticate
mykrok auth --force
```

### Rate Limit Hit
The tool automatically pauses and resumes. For large initial syncs, run overnight.

### Missing GPS Data
Some activities (treadmill, manual entries) have no GPS. They appear in sessions.tsv but not on maps.

### Photo Download Failed
Photo URLs expire. Re-run sync to retry failed photos:
```bash
mykrok sync --full
```
