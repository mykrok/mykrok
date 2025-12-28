# Export to FitTrackee

Migrate your activities to a self-hosted FitTrackee instance.

## Prerequisites

- A running FitTrackee instance
- FitTrackee account credentials
- Activities synced with MyKrok

## Step 1: Configure FitTrackee

Add FitTrackee settings to your config file (`.mykrok/config.toml`):

```toml
[fittrackee]
url = "https://fittrackee.example.com"
email = "your@email.com"
```

!!! warning "Password Security"
    Never store passwords in config files. Use the environment variable instead:
    ```bash
    export FITTRACKEE_PASSWORD="your_password"
    ```

## Step 2: Preview Export

See what would be exported without uploading:

```bash
mykrok export fittrackee --dry-run
```

Output shows:

```
Would export 150 activities to https://fittrackee.example.com
  - 120 with GPS tracks
  - 30 without GPS (will be skipped)
```

## Step 3: Export Activities

Run the export:

```bash
mykrok export fittrackee
```

Progress is shown:

```
Exporting activities to FitTrackee...
  [1/120] Morning Run (20251218T063000) - exported (workout #456)
  [2/120] Evening Ride (20251217T180000) - exported (workout #457)
  ...
Exported 120 activities, skipped 30 (no GPS)
```

## Filtering Exports

### By Date

Export only recent activities:

```bash
mykrok export fittrackee --after 2025-01-01
```

Export a specific period:

```bash
mykrok export fittrackee --after 2024-01-01 --before 2024-12-31
```

### By Limit

Export a limited number:

```bash
mykrok export fittrackee --limit 10
```

## Re-exporting

By default, already-exported activities are skipped. To re-export:

```bash
mykrok export fittrackee --force
```

## Export State

Export state is tracked in `exports/fittrackee.json`:

```json
{
  "fittrackee_url": "https://fittrackee.example.com",
  "exports": [
    {
      "ses": "20251218T063000",
      "ft_workout_id": 456,
      "exported_at": "2025-12-18T15:30:00Z"
    }
  ]
}
```

## Activity Type Mapping

Strava activity types are mapped to FitTrackee:

| Strava | FitTrackee |
|--------|------------|
| Run | Running |
| Ride | Cycling (Sport) |
| MountainBikeRide | Mountain Biking |
| Hike | Hiking |
| Walk | Walking |
| EBikeRide | Cycling (Transport) |

!!! note
    Activities without GPS tracks (treadmill, manual entries) cannot be exported to FitTrackee.

## Troubleshooting

### Authentication Failed

Check your credentials:

```bash
curl -X POST https://fittrackee.example.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"your_password"}'
```

### Export Fails

Check FitTrackee logs for upload errors. Common issues:

- File too large
- Invalid GPS data
- Unsupported activity type

### Duplicate Activities

FitTrackee may reject duplicates. Use `--force` to re-export, or delete the activity in FitTrackee first.
