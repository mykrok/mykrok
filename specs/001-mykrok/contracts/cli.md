# CLI Contract: mykrok

**Version**: 1.0.0

## Overview

Command-line interface for backing up Strava activities and managing exports.

## Testing Requirements

All CLI commands MUST have integration tests that:
1. Use Click's `CliRunner` for invocation
2. Use real fixture data from `generate_fixtures.py`
3. Verify exit codes match this contract
4. Test both text and `--json` output formats where applicable

See `specs/001-mykrok/testing.md` for detailed testing strategy.

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

**Testing Contract**: Auth requires real OAuth flow; skip in unit tests.

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

**Testing Contract**:
```python
def test_sync_creates_files(cli_runner, cli_data_dir):
    """Verify sync creates expected directory structure."""
    result = cli_runner.invoke(main, ["sync", "-d", cli_data_dir])
    assert result.exit_code == 0
    assert (cli_data_dir / "athl=alice/sessions.tsv").exists()

def test_sync_dry_run(cli_runner, cli_data_dir):
    """Verify --dry-run makes no changes."""
    before = list(cli_data_dir.rglob("*"))
    result = cli_runner.invoke(main, ["sync", "-d", cli_data_dir, "--dry-run"])
    assert result.exit_code == 0
    assert list(cli_data_dir.rglob("*")) == before

def test_sync_json_output(cli_runner, cli_data_dir):
    """Verify --json produces valid JSON with required fields."""
    result = cli_runner.invoke(main, ["sync", "-d", cli_data_dir, "--json"])
    data = json.loads(result.output)
    assert "activities_synced" in data
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

**Testing Contract**:
```python
def test_export_fittrackee_dry_run(cli_runner, cli_data_dir):
    """Verify --dry-run shows plan without uploading."""
    result = cli_runner.invoke(main, ["export", "fittrackee", "-d", cli_data_dir, "--dry-run"])
    assert result.exit_code in [0, 3]  # 0=success, 3=no activities

def test_export_fittrackee_json(cli_runner, cli_data_dir):
    """Verify --json output format."""
    result = cli_runner.invoke(main, ["export", "fittrackee", "-d", cli_data_dir, "--json", "--dry-run"])
    data = json.loads(result.output)
    assert "exported" in data or "status" in data
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

**Testing Contract**:
```python
def test_view_stats_outputs_totals(cli_runner, cli_data_dir):
    """Verify stats output includes totals."""
    result = cli_runner.invoke(main, ["view", "stats", "-d", cli_data_dir])
    assert result.exit_code == 0
    assert "Total" in result.output or "activities" in result.output.lower()

def test_view_stats_json(cli_runner, cli_data_dir):
    """Verify --json produces valid stats JSON."""
    result = cli_runner.invoke(main, ["view", "stats", "-d", cli_data_dir, "--json"])
    data = json.loads(result.output)
    assert "totals" in data

def test_view_stats_year_filter(cli_runner, cli_data_dir):
    """Verify --year filters correctly."""
    result = cli_runner.invoke(main, ["view", "stats", "-d", cli_data_dir, "--year", "2025"])
    assert result.exit_code == 0
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

**Testing Contract**:
```python
def test_gpx_generates_files(cli_runner, cli_data_dir, tmp_path):
    """Verify GPX files are generated."""
    result = cli_runner.invoke(main, ["gpx", "-d", cli_data_dir, "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    gpx_files = list(tmp_path.glob("*.gpx"))
    assert len(gpx_files) > 0

def test_gpx_valid_xml(cli_runner, cli_data_dir, tmp_path):
    """Verify generated GPX is valid XML."""
    cli_runner.invoke(main, ["gpx", "-d", cli_data_dir, "--output-dir", str(tmp_path)])
    for gpx_file in tmp_path.glob("*.gpx"):
        ET.parse(gpx_file)  # Raises if invalid XML
```

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

**Testing Contract**:
```python
def test_create_browser_generates_index(cli_runner, cli_data_dir, tmp_path):
    """Verify create-browser generates index.html."""
    result = cli_runner.invoke(main, ["create-browser", "-d", cli_data_dir, "-o", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "index.html").exists()

def test_create_browser_copies_assets(cli_runner, cli_data_dir, tmp_path):
    """Verify JavaScript assets are copied."""
    cli_runner.invoke(main, ["create-browser", "-d", cli_data_dir, "-o", str(tmp_path)])
    js_files = list(tmp_path.glob("*.js"))
    assert len(js_files) > 0
```

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

**Testing Contract**:
```python
def test_gh_pages_creates_branch(cli_runner, git_repo_with_data):
    """Verify gh-pages branch is created."""
    result = cli_runner.invoke(main, ["gh-pages", "-d", git_repo_with_data])
    assert result.exit_code == 0
    # Verify branch exists
    branches = subprocess.check_output(["git", "branch", "-a"], cwd=git_repo_with_data)
    assert b"gh-pages" in branches
```

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

**Testing Contract**:
```python
def test_rebuild_sessions_creates_tsv(cli_runner, cli_data_dir):
    """Verify rebuild-sessions creates sessions.tsv."""
    # Remove existing sessions.tsv
    for tsv in cli_data_dir.glob("**/sessions.tsv"):
        tsv.unlink()
    result = cli_runner.invoke(main, ["rebuild-sessions", "-d", cli_data_dir])
    assert result.exit_code == 0
    sessions_files = list(cli_data_dir.glob("**/sessions.tsv"))
    assert len(sessions_files) > 0

def test_rebuild_sessions_correct_count(cli_runner, cli_data_dir):
    """Verify sessions.tsv has correct row count."""
    result = cli_runner.invoke(main, ["rebuild-sessions", "-d", cli_data_dir])
    assert result.exit_code == 0
    # Count should match number of session directories
```

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

**Testing Contract**:
```python
def test_migrate_dry_run_no_changes(cli_runner, cli_data_dir):
    """Verify --dry-run makes no file changes."""
    before_mtimes = {f: f.stat().st_mtime for f in cli_data_dir.rglob("*") if f.is_file()}
    result = cli_runner.invoke(main, ["migrate", "-d", cli_data_dir, "--dry-run"])
    assert result.exit_code == 0
    after_mtimes = {f: f.stat().st_mtime for f in cli_data_dir.rglob("*") if f.is_file()}
    assert before_mtimes == after_mtimes

def test_migrate_idempotent(cli_runner, cli_data_dir):
    """Verify running migrate twice produces same result."""
    cli_runner.invoke(main, ["migrate", "-d", cli_data_dir])
    first_state = {f: f.read_bytes() for f in cli_data_dir.rglob("*.tsv")}
    cli_runner.invoke(main, ["migrate", "-d", cli_data_dir])
    second_state = {f: f.read_bytes() for f in cli_data_dir.rglob("*.tsv")}
    assert first_state == second_state
```

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
