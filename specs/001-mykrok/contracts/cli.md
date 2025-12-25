# CLI Contract: mykrok

**Version**: 1.0.0

## Overview

Command-line interface for backing up Strava activities and managing exports.

## Global Options

```
--config, -c PATH    Configuration file path (default: ~/.config/mykrok/config.toml)
--data-dir, -d PATH  Data directory path (default: ./data)
--verbose, -v        Increase verbosity (can be repeated: -v, -vv, -vvv)
--quiet, -q          Suppress non-error output
--json               Output in JSON format (for machine parsing)
--help, -h           Show help message
--version            Show version number
```

## Commands

### `mykrok auth`

Authenticate with Strava OAuth2.

```
mykrok auth [OPTIONS]

Options:
  --client-id ID       Strava API client ID
  --client-secret KEY  Strava API client secret
  --port PORT          Local OAuth callback port (default: 8000)
  --force              Force re-authentication even if token exists
```

**Exit Codes**:
- 0: Success
- 1: Authentication failed
- 2: Invalid credentials

**Output** (JSON mode):
```json
{
  "status": "success",
  "athlete_id": 12345,
  "username": "athlete123",
  "token_expires_at": "2025-12-18T12:00:00Z"
}
```

---

### `mykrok sync`

Synchronize activities from Strava.

```
mykrok sync [OPTIONS]

Options:
  --what MODE          Sync mode: recent (default), full, or social
  --after DATE         Only sync activities after this date (ISO 8601)
  --before DATE        Only sync activities before this date (ISO 8601)
  --limit N            Maximum number of activities to sync
  --no-photos          Skip photo download
  --no-streams         Skip GPS/sensor stream download
  --no-comments        Skip comments and kudos download
  --exclude PATTERN    Regex pattern to exclude athletes (can be repeated)
  --dry-run            Show what would be synced without downloading
```

**Sync Modes (`--what`)**:
- `recent` (default): Incremental sync of new activities since last sync
- `full`: Sync all activities from Strava (ignores last sync time)
- `social`: Only refresh kudos/comments for existing local activities without
  re-downloading GPS data or photos. Useful for updating social metadata after
  bug fixes or to capture new kudos/comments.
- `athlete-profiles`: Refresh athlete profile information (name, location) and
  download avatar photos. Updates athletes.tsv with profile data.
- `check-and-fix`: Verify data integrity and repair missing photos/tracking data.
  Detects related sessions (same activity from different devices) and cross-links
  photos between them. Use `--dry-run` to preview without making changes.

**Exit Codes**:
- 0: Success (activities synced)
- 0: Success (no new activities)
- 1: API error
- 2: Authentication required
- 3: Rate limit exceeded (will resume)

**Output** (text mode):
```
Syncing activities for athlete123...
  [1/10] Morning Run (20251218T063000) - 5.2 km
  [2/10] Evening Walk (20251217T180000) - 2.1 km
  ...
Synced 10 activities (3 new, 7 updated)
```

**Output** (JSON mode):
```json
{
  "status": "success",
  "athlete": "athlete123",
  "activities_synced": 10,
  "activities_new": 3,
  "activities_updated": 7,
  "photos_downloaded": 5,
  "errors": []
}
```

---

### `mykrok export fittrackee`

Export activities to FitTrackee.

```
mykrok export fittrackee [OPTIONS]

Options:
  --url URL            FitTrackee instance URL (required)
  --email EMAIL        FitTrackee account email
  --password PASS      FitTrackee account password (or use env: FITTRACKEE_PASSWORD)
  --after DATE         Only export activities after this date
  --before DATE        Only export activities before this date
  --limit N            Maximum number of activities to export
  --force              Re-export already exported activities
  --dry-run            Show what would be exported without uploading
```

**Exit Codes**:
- 0: Success
- 1: FitTrackee API error
- 2: Authentication failed
- 3: No activities to export

**Output** (JSON mode):
```json
{
  "status": "success",
  "exported": 5,
  "skipped": 10,
  "failed": 0,
  "details": [
    {"ses": "20251218T063000", "ft_workout_id": 123, "status": "exported"},
    {"ses": "20251217T180000", "status": "skipped", "reason": "no_gps"}
  ]
}
```

---

### `mykrok view stats`

Display activity statistics.

```
mykrok view stats [OPTIONS]

Options:
  --year YEAR          Show stats for specific year
  --month YYYY-MM      Show stats for specific month
  --after DATE         Stats for activities after this date
  --before DATE        Stats for activities before this date
  --type TYPE          Filter by activity type
  --by-month           Break down by month
  --by-type            Break down by activity type
```

**Output** (text mode):
```
Statistics for 2025:

  Total Activities: 150
  Total Distance: 1,234.5 km
  Total Time: 123h 45m
  Total Elevation: 12,345 m

  By Type:
    Run: 100 activities, 500.0 km
    Ride: 40 activities, 700.0 km
    Hike: 10 activities, 34.5 km
```

**Output** (JSON mode):
```json
{
  "period": {"year": 2025},
  "totals": {
    "activities": 150,
    "distance_km": 1234.5,
    "time_hours": 123.75,
    "elevation_m": 12345
  },
  "by_type": {
    "Run": {"activities": 100, "distance_km": 500.0},
    "Ride": {"activities": 40, "distance_km": 700.0},
    "Hike": {"activities": 10, "distance_km": 34.5}
  }
}
```

---

### `mykrok gpx`

Export activities as GPX files.

```
mykrok gpx [OPTIONS] [SESSION...]

Options:
  --output-dir PATH    Output directory (default: ./gpx)
  --after DATE         Export activities after this date
  --before DATE        Export activities before this date
  --with-hr            Include heart rate in GPX extensions
  --with-cadence       Include cadence in GPX extensions
  --with-power         Include power in GPX extensions
```

**Exit Codes**:
- 0: Success
- 1: No activities to export
- 2: Output write error

---

### `mykrok create-browser`

Generate interactive activity browser (static SPA).

```
mykrok create-browser [OPTIONS]

Options:
  --serve              Start local HTTP server after generation
  --port PORT          Server port (default: 8080)
```

Creates a single-page application (SPA) with:
- Map view with activity markers and tracks
- Sessions list with filtering and search
- Statistics view with charts

The browser loads data on demand from the data directory (athletes.tsv,
sessions.tsv, tracking.parquet files).

**Prerequisite**: Data directory must contain `athletes.tsv` (run `mykrok sync` first).

**Exit Codes**:
- 0: Success
- 1: Invalid data directory (missing athletes.tsv)

---

### `mykrok gh-pages`

Generate GitHub Pages demo website with synthetic data.

```
mykrok gh-pages [OPTIONS]

Options:
  --push               Push gh-pages branch to origin after generating
  --worktree PATH      Path for gh-pages worktree (default: .gh-pages)
  --no-datalad         Don't use datalad even if available
  --seed INT           Random seed for reproducible demo data (default: 42)
```

Creates or updates a gh-pages branch with a live demo of the
mykrok web frontend using reproducible synthetic data.

**Exit Codes**:
- 0: Success
- 1: Git operation failed

---

### `mykrok rebuild-sessions`

Regenerate sessions.tsv from activity info.json files.

```
mykrok rebuild-sessions [OPTIONS]

Options:
  --athlete USERNAME   Rebuild for specific athlete only
```

Scans all activity directories and regenerates sessions.tsv with
current schema. Useful after schema changes or data corruption.

**Exit Codes**:
- 0: Success
- 1: No activities found

---

### `mykrok migrate`

Run data migrations for schema changes.

```
mykrok migrate [OPTIONS]

Options:
  --dry-run            Show what would be changed without modifying files
```

Available migrations:
- Rename `center_lat`/`center_lng` to `start_lat`/`start_lng` in sessions.tsv

**Exit Codes**:
- 0: Success (or no migrations needed)
- 1: Migration failed

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `STRAVA_CLIENT_ID` | Strava API client ID |
| `STRAVA_CLIENT_SECRET` | Strava API client secret |
| `MYKROK_CONFIG` | Config file path (overrides default) |
| `MYKROK_DATA_DIR` | Data directory path |
| `FITTRACKEE_URL` | FitTrackee instance URL |
| `FITTRACKEE_EMAIL` | FitTrackee account email |
| `FITTRACKEE_PASSWORD` | FitTrackee account password |

> **Legacy support**: `STRAVA_BACKUP_CONFIG` and `STRAVA_BACKUP_DATA_DIR` are still recognized for backward compatibility.

---

## Configuration File

Default location: `~/.config/mykrok/config.toml`

```toml
[strava]
client_id = "12345"
client_secret = "secret"

[strava.exclude]
athletes = ["^bot.*", ".*test.*"]  # Regex patterns

[data]
directory = "/path/to/backup"

[fittrackee]
url = "https://fittrackee.example.com"
email = "user@example.com"
# password stored in keyring or env var

[sync]
photos = true
streams = true
comments = true
```

---

## Exit Code Summary

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication/authorization error |
| 3 | Rate limit / resource exhausted |
| 4 | Configuration error |
| 5 | Network error |
