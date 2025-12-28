# Configuration

MyKrok uses TOML configuration files for storing settings.

## Configuration File Location

MyKrok looks for configuration in these locations (in order):

1. `MYKROK_CONFIG` environment variable (explicit path)
2. `.mykrok/config.toml` in current directory
3. `~/.config/mykrok/config.toml` (user default)

!!! note "Legacy Support"
    `.strava-backup/config.toml` and `.strava-backup.toml` are still recognized for backward compatibility.

## Configuration File Format

```toml
[strava]
client_id = "12345"
client_secret = "your_client_secret"

[strava.exclude]
athletes = ["^bot.*", ".*test.*"]  # Regex patterns

[data]
directory = "/path/to/backup"

[sync]
photos = true
streams = true
comments = true

[fittrackee]
url = "https://fittrackee.example.com"
email = "user@example.com"
# password stored in keyring or env var
```

## Sections

### `[strava]`

Strava API credentials and settings.

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `client_id` | string | Yes | Strava API client ID |
| `client_secret` | string | Yes | Strava API client secret |

### `[strava.exclude]`

Patterns to exclude from sync.

| Key | Type | Description |
|-----|------|-------------|
| `athletes` | array | Regex patterns to exclude athletes |

### `[data]`

Data storage settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `directory` | string | `./data` | Path to data directory |

### `[sync]`

Sync behavior settings.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `photos` | boolean | `true` | Download activity photos |
| `streams` | boolean | `true` | Download GPS/sensor streams |
| `comments` | boolean | `true` | Download comments and kudos |

### `[fittrackee]`

FitTrackee export settings.

| Key | Type | Description |
|-----|------|-------------|
| `url` | string | FitTrackee instance URL |
| `email` | string | FitTrackee account email |

!!! warning "Security"
    Never store passwords in config files. Use environment variables (`FITTRACKEE_PASSWORD`) or a keyring.

## OAuth Tokens

OAuth tokens are stored separately in `.mykrok/oauth-tokens.toml`. This file is automatically gitignored and should never be committed.

```toml
[athlete_12345]
access_token = "..."
refresh_token = "..."
expires_at = 1735056000
```

## Environment Variables

All configuration can be overridden with environment variables:

| Variable | Config Equivalent |
|----------|-------------------|
| `STRAVA_CLIENT_ID` | `strava.client_id` |
| `STRAVA_CLIENT_SECRET` | `strava.client_secret` |
| `MYKROK_DATA_DIR` | `data.directory` |
| `FITTRACKEE_URL` | `fittrackee.url` |
| `FITTRACKEE_EMAIL` | `fittrackee.email` |
| `FITTRACKEE_PASSWORD` | FitTrackee password |

## Example Configurations

### Minimal Configuration

```toml
[strava]
client_id = "12345"
client_secret = "secret"
```

### Full Configuration

```toml
[strava]
client_id = "12345"
client_secret = "secret"

[strava.exclude]
athletes = ["^bot_", "test_user"]

[data]
directory = "/home/user/fitness-backup/data"

[sync]
photos = true
streams = true
comments = true

[fittrackee]
url = "https://fittrackee.example.com"
email = "user@example.com"
```
