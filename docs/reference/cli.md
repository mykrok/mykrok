# CLI Commands

Complete reference for the `mykrok` command-line interface.

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

```bash
mykrok auth [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--client-id ID` | Strava API client ID |
| `--client-secret KEY` | Strava API client secret |
| `--port PORT` | Local OAuth callback port (default: 8000) |
| `--force` | Force re-authentication even if token exists |

**Exit Codes:**

- `0`: Success
- `1`: Authentication failed
- `2`: Invalid credentials

---

### `mykrok sync`

Synchronize activities from Strava.

```bash
mykrok sync [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--what MODE` | Sync mode (see below) |
| `--after DATE` | Only sync activities after this date (ISO 8601) |
| `--before DATE` | Only sync activities before this date (ISO 8601) |
| `--limit N` | Maximum number of activities to sync |
| `--no-photos` | Skip photo download |
| `--no-streams` | Skip GPS/sensor stream download |
| `--no-comments` | Skip comments and kudos download |
| `--exclude PATTERN` | Regex pattern to exclude athletes (repeatable) |
| `--dry-run` | Show what would be synced without downloading |
| `--lean-update` | Skip sync if local data is already current |

**Sync Modes (`--what`):**

| Mode | Description |
|------|-------------|
| `recent` | Incremental sync of new activities since last sync (default) |
| `full` | Sync all activities from Strava |
| `social` | Refresh kudos/comments without re-downloading GPS data |
| `athlete-profiles` | Refresh athlete profiles and avatars |
| `check-and-fix` | Verify data integrity and repair missing data |

**Exit Codes:**

- `0`: Success
- `1`: API error
- `2`: Authentication required
- `3`: Rate limit exceeded

---

### `mykrok view stats`

Display activity statistics.

```bash
mykrok view stats [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--year YEAR` | Show stats for specific year |
| `--month YYYY-MM` | Show stats for specific month |
| `--after DATE` | Stats for activities after this date |
| `--before DATE` | Stats for activities before this date |
| `--type TYPE` | Filter by activity type |
| `--by-month` | Break down by month |
| `--by-type` | Break down by activity type |

---

### `mykrok create-browser`

Generate interactive activity browser.

```bash
mykrok create-browser [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output filename (default: mykrok.html) |
| `--serve` | Start local HTTP server after generation |
| `--port PORT` | Server port (default: 8080) |

Creates a single-page application with:

- Map view with activity markers and tracks
- Sessions list with filtering and search
- Statistics view with charts

!!! note "Prerequisite"
    Data directory must contain `athletes.tsv` (run `mykrok sync` first).

---

### `mykrok gpx`

Export activities as GPX files.

```bash
mykrok gpx [OPTIONS] [SESSION...]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--output-dir PATH` | Output directory (default: ./gpx) |
| `--after DATE` | Export activities after this date |
| `--before DATE` | Export activities before this date |
| `--with-hr` | Include heart rate in GPX extensions |
| `--with-cadence` | Include cadence in GPX extensions |
| `--with-power` | Include power in GPX extensions |

---

### `mykrok export fittrackee`

Export activities to FitTrackee.

```bash
mykrok export fittrackee [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--url URL` | FitTrackee instance URL (required) |
| `--email EMAIL` | FitTrackee account email |
| `--password PASS` | FitTrackee account password |
| `--after DATE` | Only export activities after this date |
| `--before DATE` | Only export activities before this date |
| `--limit N` | Maximum number of activities to export |
| `--force` | Re-export already exported activities |
| `--dry-run` | Show what would be exported |

---

### `mykrok gh-pages`

Generate GitHub Pages demo website.

```bash
mykrok gh-pages [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--push` | Push gh-pages branch to origin |
| `--worktree PATH` | Path for gh-pages worktree |
| `--no-datalad` | Don't use datalad even if available |
| `--seed INT` | Random seed for demo data (default: 42) |

---

### `mykrok rebuild-sessions`

Regenerate sessions.tsv from activity info.json files.

```bash
mykrok rebuild-sessions [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--athlete USERNAME` | Rebuild for specific athlete only |

---

### `mykrok migrate`

Run data migrations for schema changes.

```bash
mykrok migrate [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--dry-run` | Show what would be changed |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `STRAVA_CLIENT_ID` | Strava API client ID |
| `STRAVA_CLIENT_SECRET` | Strava API client secret |
| `MYKROK_CONFIG` | Config file path |
| `MYKROK_DATA_DIR` | Data directory path |
| `FITTRACKEE_URL` | FitTrackee instance URL |
| `FITTRACKEE_EMAIL` | FitTrackee account email |
| `FITTRACKEE_PASSWORD` | FitTrackee account password |

!!! note "Legacy Support"
    `STRAVA_BACKUP_CONFIG` and `STRAVA_BACKUP_DATA_DIR` are still recognized for backward compatibility.

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Authentication/authorization error |
| 3 | Rate limit / resource exhausted |
| 4 | Configuration error |
| 5 | Network error |
