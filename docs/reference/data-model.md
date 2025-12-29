# Data Model

MyKrok stores activities in a Hive-partitioned directory structure optimized for both human readability and efficient querying with tools like DuckDB.

## Directory Structure

```
data/
├── athletes.tsv                    # Summary of all athletes
├── mykrok.html                     # Generated map browser
└── athl={username}/                # Per-athlete directory
    ├── athlete.json                # Profile data
    ├── avatar.jpg                  # Profile photo
    ├── sessions.tsv                # Activity index
    ├── gear.json                   # Equipment catalog
    └── ses={datetime}/             # Per-activity directory
        ├── info.json               # Activity metadata
        ├── tracking.parquet        # GPS + sensor data
        ├── tracking.json           # Data manifest
        └── photos/
            └── {timestamp}.jpg     # Activity photos
```

## Entities

### Athlete

Profile data for the authenticated user.

**Storage:** `athl={username}/athlete.json`

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Strava athlete ID |
| `username` | string | Strava username |
| `firstname` | string | First name |
| `lastname` | string | Last name |
| `city` | string | City from profile |
| `country` | string | Country from profile |
| `profile_url` | string | Profile image URL |

### Activity

Athletic activity with metadata.

**Storage:** `ses={datetime}/info.json`

The `datetime` format is ISO 8601 basic (e.g., `20251218T143022`).

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Strava activity ID |
| `name` | string | Activity title |
| `type` | string | Activity type (Run, Ride, etc.) |
| `sport_type` | string | Specific sport type |
| `start_date` | datetime | Start time (UTC) |
| `distance` | float | Distance in meters |
| `moving_time` | integer | Moving time in seconds |
| `elapsed_time` | integer | Total time in seconds |
| `total_elevation_gain` | float | Elevation gain in meters |
| `average_heartrate` | float | Average heart rate |
| `max_heartrate` | integer | Maximum heart rate |
| `average_watts` | float | Average power |
| `kudos_count` | integer | Number of kudos |
| `comment_count` | integer | Number of comments |

**Nested data in info.json:**

- `comments[]` - Array of comment objects
- `kudos[]` - Array of kudo objects
- `laps[]` - Array of lap data
- `photos[]` - Array of photo metadata

### Track (GPS/Sensor Data)

Time-series data stored as Parquet for efficient querying.

**Storage:** `ses={datetime}/tracking.parquet`

| Column | Type | Description |
|--------|------|-------------|
| `time` | float64 | Seconds from start |
| `lat` | float64 | Latitude |
| `lng` | float64 | Longitude |
| `altitude` | float32 | Elevation in meters |
| `distance` | float32 | Cumulative distance |
| `heartrate` | int16 | Heart rate (BPM) |
| `cadence` | int16 | Cadence |
| `watts` | int16 | Power |
| `temp` | float32 | Temperature (°C) |

A manifest file (`tracking.json`) describes available columns:

```json
{
  "columns": ["time", "lat", "lng", "altitude", "heartrate"],
  "row_count": 3600,
  "has_gps": true,
  "has_hr": true,
  "has_power": false
}
```

### Sessions Summary

Denormalized index for quick filtering.

**Storage:** `athl={username}/sessions.tsv`

| Column | Type | Description |
|--------|------|-------------|
| `datetime` | string | ISO 8601 basic format (UTC) |
| `datetime_local` | string | ISO 8601 basic format (local time) |
| `type` | string | Activity type |
| `sport` | string | Sport type |
| `name` | string | Activity name |
| `distance_m` | float | Distance in meters |
| `moving_time_s` | integer | Moving time (seconds) |
| `elevation_gain_m` | float | Elevation gain |
| `avg_hr` | float | Average heart rate |
| `has_gps` | boolean | Has GPS data |
| `has_photos` | boolean | Has photos |
| `start_lat` | float | Starting latitude |
| `start_lng` | float | Starting longitude |

### Athletes Summary

Top-level index of all athletes.

**Storage:** `data/athletes.tsv`

| Column | Type | Description |
|--------|------|-------------|
| `username` | string | Athlete username |
| `firstname` | string | First name |
| `lastname` | string | Last name |
| `session_count` | integer | Number of activities |
| `total_distance_km` | float | Total distance |
| `activity_types` | string | Comma-separated types |

## Querying with DuckDB

```sql
-- Total distance by sport
SELECT sport, SUM(distance_m)/1000 as km, COUNT(*) as activities
FROM read_csv_auto('data/athl=*/sessions.tsv')
GROUP BY sport
ORDER BY km DESC;

-- Average heart rate by activity
SELECT datetime, name, avg_hr, max_hr
FROM read_csv_auto('data/athl=*/sessions.tsv')
WHERE avg_hr > 0
ORDER BY datetime DESC
LIMIT 10;

-- Query GPS tracks
SELECT ses, AVG(heartrate) as avg_hr, MAX(altitude) as max_alt
FROM read_parquet('data/**/tracking.parquet', hive_partitioning=true)
WHERE heartrate > 0
GROUP BY ses;
```

## File Format Details

### Why Parquet?

GPS and sensor data is stored as Parquet because:

- **Columnar format** - Efficient for analytics queries
- **Compression** - 5-10x smaller than CSV
- **Browser support** - hyparquet enables direct browser reading
- **Type safety** - Schema preserved

### Why TSV?

Summary files use TSV (Tab-Separated Values) because:

- **Human readable** - Easy to inspect and edit
- **Git-friendly** - Clean diffs
- **Universal** - Works with any tool
- **DuckDB compatible** - Direct querying
