# MyKrok

[![Documentation Status](https://readthedocs.org/projects/mykrok/badge/?version=latest)](https://mykrok.readthedocs.io/en/latest/)

> **Note**: This project was formerly known as "mykrok". The name "MyKrok" comes from Ukrainian "мій крок" meaning "my step" - fitting for a tool that preserves every step of your fitness journey.

CLI tool to backup fitness activities with incremental sync, map visualization, and export capabilities. Currently supports **Strava** as the data source.

**[Live Demo](https://mykrok.github.io/mykrok/)** - Try the web frontend with synthetic data. It is served directly from [gh-pages branch](https://github.com/mykrok/mykrok/tree/gh-pages) where you could also explore the backup filetree we show [below](#no-backend-required).

## Features

- **Backup Activities**: Download all your activities including metadata, GPS tracks, photos, comments, and kudos
- **Incremental Sync**: Only fetch new activities after initial backup
- **Interactive Maps**: Generate HTML maps with route visualization and heatmap mode
- **Statistics**: View activity statistics by time period with breakdowns by type
- **Offline Browsing**: Browse your backed-up activities locally without internet
- **FitTrackee Export**: Export activities to self-hosted FitTrackee instances

## Screenshots

The unified web frontend provides a complete activity browsing experience.
Screenshots are auto-generated from the demo dataset (`tox -e screenshots`).

### Map View

![Map view with activity markers](docs/screenshots/01-map-overview.jpg)
*Map view with activity markers*

![Activities zoomed to fit](docs/screenshots/02-map-zoomed.jpg)
*Activities zoomed to fit*

![Activity popup with details](docs/screenshots/03-map-popup.jpg)
*Activity popup with details*

### Sessions View

![Sessions list with filters](docs/screenshots/04-sessions-list.jpg)
*Sessions list with filters*

![Sessions filtered by type](docs/screenshots/05-sessions-filtered.jpg)
*Sessions filtered by type*

![Session detail panel](docs/screenshots/06-session-detail.jpg)
*Session detail panel*

### Session Detail

![Full-screen session view](docs/screenshots/07-session-full.jpg)
*Full-screen session view*

![Activity data streams](docs/screenshots/08-data-streams.jpg)
*Activity data streams (elevation, heart rate, cadence)*

### Statistics

![Statistics dashboard](docs/screenshots/09-stats-dashboard.jpg)
*Statistics dashboard*

![Statistics by athlete](docs/screenshots/10-stats-filtered.jpg)
*Statistics by athlete*

### No Backend Required

The web UI loads data **directly from the file tree** — no database, no server-side processing, no custom data structures. Just standard formats (TSV, JSON, Parquet) served as static files:

```
data/
├── athletes.tsv                    # List of athletes
├── athl=alice/
│   ├── sessions.tsv                # Activity index (dates, distances, stats)
│   └── ses=20241218T063000/
│       ├── info.json               # Activity metadata
│       ├── tracking.parquet        # GPS + sensor streams (lat, lng, hr, cadence...)
│       └── photos/
│           └── photo_1.jpg
└── athl=bob/
    ├── sessions.tsv
    └── ses=20241218T063000/        # Shared run (same datetime)
        ├── info.json
        └── tracking.parquet
```

The browser fetches `athletes.tsv` → discovers athletes → loads each `sessions.tsv` → renders the map/table. Clicking an activity fetches its `tracking.parquet` directly. This means you can:

- **Host anywhere**: Any static file server (nginx, GitHub Pages, S3, local `python -m http.server`)
- **Query with standard tools**: DuckDB, pandas, or any Parquet-compatible tool
- **Version with git/DataLad**: Text files diff cleanly, binary files handled by git-annex
- **Browse offline**: Open `mykrok.html` directly from disk

## Installation

```bash
# Clone repository
git clone https://github.com/mykrok/mykrok
cd mykrok

# Install with uv (recommended)
uv venv
source .venv/bin/activate
uv pip install -e ".[devel]"

# Or with pip
pip install -e ".[devel]"
```

## Strava API Setup

Before using MyKrok, you need to create a Strava API application:

1. Go to https://www.strava.com/settings/api
2. Click "Create an Application" (or use existing one)
3. Fill in the form:
   - **Application Name**: e.g., "My Backup Tool"
   - **Category**: "Personal"
   - **Website**: "http://localhost" (or your own)
   - **Authorization Callback Domain**: "localhost"
4. After creation, note your **Client ID** and **Client Secret**

## Quick Start

1. Authenticate with your Strava API credentials:
   ```bash
   mykrok auth --client-id YOUR_CLIENT_ID --client-secret YOUR_CLIENT_SECRET
   ```
   This opens a browser for OAuth authorization. After approval, tokens are saved automatically.

2. Sync your activities:
   ```bash
   mykrok sync
   ```

3. View your data:
   ```bash
   mykrok view stats
   mykrok create-browser --serve
   ```

## Configuration

MyKrok looks for configuration in the following order:

1. `MYKROK_CONFIG` environment variable (explicit path)
2. `.mykrok/config.toml` in the current directory (recommended for DataLad datasets)
3. `.mykrok/config.toml` in the current directory (legacy, still supported)
4. `.mykrok.toml` in the current directory (legacy, still supported)
5. `~/.config/mykrok/config.toml`

OAuth tokens are stored separately in `.mykrok/oauth-tokens.toml` (gitignored).

### Configuration File Format

Create `.mykrok/config.toml` in your project directory or `~/.config/mykrok/config.toml`:

```toml
[strava]
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
# These are auto-populated after `mykrok auth`:
# access_token = "..."
# refresh_token = "..."
# token_expires_at = 1234567890

[data]
directory = "./data"  # Where to store backed-up activities

[sync]
photos = true    # Download activity photos
streams = true   # Download GPS/sensor data
comments = true  # Download comments and kudos

[fittrackee]
url = "https://fittrackee.example.com"
email = "your@email.com"
# password can be set via FITTRACKEE_PASSWORD env var
```

### Environment Variables

All settings can be overridden with environment variables:

| Variable | Description |
|----------|-------------|
| `MYKROK_CONFIG` | Path to config file |
| `STRAVA_CLIENT_ID` | Strava API client ID |
| `STRAVA_CLIENT_SECRET` | Strava API client secret |
| `MYKROK_DATA_DIR` | Data storage directory |
| `FITTRACKEE_URL` | FitTrackee instance URL |
| `FITTRACKEE_EMAIL` | FitTrackee login email |
| `FITTRACKEE_PASSWORD` | FitTrackee login password |

## Commands

### Authentication

```bash
# First-time authentication
mykrok auth --client-id YOUR_ID --client-secret YOUR_SECRET

# Re-authenticate (e.g., after token expiry)
mykrok auth --force
```

### Sync Activities

```bash
# Incremental sync (default) - only new activities since last sync
mykrok sync

# Full sync - re-download all activities
mykrok sync --what=full

# Refresh social data (kudos/comments) for existing activities
mykrok sync --what=social

# Refresh athlete profile info and avatar
mykrok sync --what=athlete-profiles

# Sync with limits
mykrok sync --limit 100

# Preview without downloading
mykrok sync --dry-run

# Skip photos/comments
mykrok sync --no-photos --no-comments

# Sync specific activities by ID
mykrok sync --activity-ids 12345678901,12345678902
```

### View Statistics

```bash
# Overall stats
mykrok view stats

# Stats for specific year
mykrok view stats --year 2025

# Stats for specific month
mykrok view stats --month 2025-06

# Breakdown by month
mykrok view stats --by-month

# Breakdown by activity type
mykrok view stats --by-type

# JSON output
mykrok view stats --json
```

### Generate Interactive Browser

```bash
# Generate and serve locally
mykrok create-browser --serve

# Custom port
mykrok create-browser --serve --port 9000

# Generate without serving
mykrok create-browser

# Custom output filename
mykrok create-browser --output my-activities.html
```

The browser includes:
- Interactive map with activity markers and GPS tracks
- Sessions list with filtering by date, type, and search
- Statistics dashboard with charts
- Heatmap layer toggle
- Photo viewing
- Offline support (works without internet)

### Export GPX

```bash
# Export specific activity
mykrok gpx 12345678901 --output activity.gpx

# Export all activities
mykrok gpx --all --output-dir ./gpx/
```

### Export to FitTrackee

```bash
# Export to FitTrackee
mykrok export fittrackee --url https://fittrackee.example.com --email user@example.com

# Preview what would be exported
mykrok export fittrackee --dry-run

# Force re-export all
mykrok export fittrackee --full
```

### Create DataLad Dataset

Create a version-controlled dataset for reproducible backups using [DataLad](https://www.datalad.org/):

```bash
# Create a new DataLad dataset
mykrok create-datalad-dataset ./my-backup

# Navigate to the dataset
cd my-backup

# Edit config with your Strava API credentials
nano .mykrok/config.toml

# Authenticate
mykrok auth

# Sync using datalad run (creates versioned commit)
make sync

# Generate interactive browser for web viewing
mykrok create-browser
```

This creates a dataset with:
- **text2git configuration**: Text files (JSON, TSV) tracked by git, binary files (photos, Parquet) by git-annex
- **Sample config**: `.mykrok/config.toml` with comments explaining each setting
- **README**: Documentation for the dataset
- **Makefile**: Targets for `make sync`, `make stats`, `make map`, etc. using `datalad run`

Benefits of DataLad integration:
- Full version history of all backups
- Reproducible sync operations with `datalad run`
- Efficient storage of binary files with git-annex
- Easy to clone and share datasets
- Simple publishing to web servers (see below)

### Publishing to a Web Server

With DataLad, publishing your backup to a web server for browser-based viewing is trivial:

```bash
# Create a sibling that excludes sensitive files (API credentials)
datalad create-sibling -s public-website \
    --annex-wanted "not metadata=distribution-restrictions=*" \
    user@server.example.com:/var/www/mykrok

# Push your data (sensitive config files are automatically excluded)
datalad push --to=public-website
```

Then access the map visualization at `https://your-server.example.com/mykrok/mykrok.html`.

**Note**: Access restrictions and user management are outside the scope of this project. Implement access control using your web server's authentication mechanisms (HTTP Basic Auth, OAuth proxy, IP allowlisting, etc.).

## Data Storage

Activities are stored in a Hive-partitioned directory structure:

```
data/
├── athletes.tsv                  # Summary of all athletes
├── mykrok.html                   # Generated interactive browser
└── athl={username}/
    ├── athlete.json              # Athlete profile data
    ├── avatar.jpg                # Profile photo
    ├── sessions.tsv              # Activity summary (TSV format)
    ├── gear.json                 # Equipment catalog
    └── ses={datetime}/           # Individual activity folder
        ├── info.json             # Activity metadata, comments, kudos
        ├── tracking.parquet      # GPS + sensor data (Parquet)
        ├── tracking.json         # Data manifest
        └── photos/               # Activity photos
            └── 20251218T063500.jpg
```

### Query with DuckDB

```bash
duckdb
```

```sql
-- Activity summary
SELECT sport, SUM(distance_m)/1000 as km, COUNT(*) as activities
FROM read_csv_auto('data/athl=*/sessions.tsv')
GROUP BY sport;

-- GPS track analysis
SELECT ses, AVG(heartrate) as avg_hr, MAX(heartrate) as max_hr
FROM read_parquet('data/**/tracking.parquet', hive_partitioning=true)
WHERE heartrate > 0
GROUP BY ses;
```

## Cron Setup

For automated daily backups:

```bash
# Edit crontab
crontab -e

# Add daily sync at 2 AM
0 2 * * * cd /path/to/mykrok && .venv/bin/mykrok sync --quiet
```

## Troubleshooting

### Token Expired
```bash
mykrok auth --force
```

### Rate Limit Hit
The tool automatically pauses when hitting Strava's rate limits (200 requests/15 minutes, 1000/day) and resumes. For large initial syncs, the process may span multiple days.

### Missing GPS Data
Some activities (treadmill, manual entries) have no GPS. They appear in `sessions.tsv` but not on maps.

### Photo Download Failed
Photo URLs expire. Re-run sync to retry:
```bash
mykrok sync --full
```

## License

Apache 2.0
