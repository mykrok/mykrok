# Recover Photos

Fix missing photos and verify data integrity.

## Understanding Photo Issues

Photos can be missing for several reasons:

- Download failed during initial sync
- Strava photo URLs expired
- Network interruption
- Related sessions have photos on different devices

## Check for Issues

Run the check-and-fix mode in dry-run:

```bash
mykrok sync --what check-and-fix --dry-run
```

This reports:

```
Checking data integrity...
  Activity 20251218T063000: 2 photos missing
  Activity 20251217T180000: tracking.parquet missing
  Activity 20251216T120000: related session has 3 photos
Found 5 issues (3 fixable)
```

## Fix Missing Photos

Run without `--dry-run` to fix:

```bash
mykrok sync --what check-and-fix
```

This:

1. Re-downloads photos with expired URLs
2. Copies photos from related sessions
3. Rebuilds tracking data if source available

## Related Sessions

MyKrok detects "related sessions" - the same activity recorded on different devices (e.g., phone + watch). Photos from one device are automatically linked to the other.

```json
{
  "related_sessions": ["20251218T063001", "20251218T063002"]
}
```

## Re-sync Specific Activities

To force re-download of a specific activity:

```bash
# Delete the session directory
rm -rf data/athl=username/ses=20251218T063000

# Re-sync
mykrok sync --full --limit 1 --after 2025-12-18 --before 2025-12-19
```

## Full Re-sync

If many photos are missing:

```bash
mykrok sync --full
```

This re-downloads all activities (metadata is updated, existing files preserved).

## Manual Photo Recovery

If automatic recovery fails:

1. Find the activity on Strava web
2. Download photos manually
3. Save to `data/athl=username/ses=datetime/photos/`
4. Name format: `YYYYMMDDTHHMMSS.jpg`

## Verify Photos

After recovery, verify your data:

```bash
# Count photos per activity
find data -name "*.jpg" -path "*/photos/*" | wc -l

# List activities with photos
grep -l "has_photos.*true" data/athl=*/ses=*/info.json
```

## Troubleshooting

### "Photo URL expired"

Strava photo URLs expire after some time. Re-running sync fetches fresh URLs.

### "Photo not found on Strava"

The photo was deleted from Strava. It cannot be recovered.

### "Already exists"

The photo is already downloaded. No action needed.

### Network Errors

Retry after checking connectivity:

```bash
mykrok sync --what check-and-fix
```
