# Data Model: Strava Activity Backup

**Branch**: `001-strava-backup` | **Date**: 2025-12-18

## Entity Relationship Diagram

```
┌──────────────────┐
│     Athlete      │ 1
│ (athl={username})│────────────────────────┐
└────────┬─────────┘                        │
         │ 1                                │
         │                                  │
         ▼ *                                ▼ *
┌──────────────────┐                ┌──────────────────┐
│    Activity      │                │      Gear        │
│(ses={datetime})  │                │   (gear.json)    │
└────────┬─────────┘                └──────────────────┘
         │ 1
         │
    ┌────┼────┬─────────┐
    │    │    │         │
    ▼ 1  ▼ *  ▼ *       ▼ *
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Track │ │Photo │ │Comment│ │ Kudo │
│      │ │      │ │      │ │      │
└──────┘ └──────┘ └──────┘ └──────┘
```

## Entities

### Athlete

**Description**: The authenticated Strava user whose data is being backed up.

**Storage**: Directory partition `athl={username}/`

**Fields** (stored in `athlete.json`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | Yes | Strava athlete ID |
| username | string | Yes | Strava username (URL-safe) |
| firstname | string | No | Athlete first name |
| lastname | string | No | Athlete last name |
| city | string | No | City from profile |
| country | string | No | Country from profile |
| profile_url | string | No | Profile image URL |

**Files**:
- `athlete.json`: Athlete profile data
- `avatar.{jpg|png}`: Profile photo (downloaded from profile_url)
- `sessions.tsv`: Summary of all activities for this athlete
- `gear.json`: Equipment catalog

---

### Activity

**Description**: An athletic activity with metadata, associated GPS track, photos, comments, and kudos.

**Storage**: Directory partition `ses={datetime}/` where datetime is ISO 8601 basic format (e.g., `20251218T143022`)

**Fields** (stored in `info.json`):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | Yes | Strava activity ID |
| name | string | Yes | Activity title |
| description | string | No | Activity description |
| type | string | Yes | Activity type (Run, Ride, Hike, etc.) |
| sport_type | string | Yes | Specific sport type |
| start_date | datetime | Yes | Activity start time (UTC) |
| start_date_local | datetime | Yes | Activity start time (local timezone) |
| timezone | string | Yes | Timezone identifier |
| distance | float | Yes | Total distance in meters |
| moving_time | integer | Yes | Moving time in seconds |
| elapsed_time | integer | Yes | Total elapsed time in seconds |
| total_elevation_gain | float | No | Elevation gain in meters |
| calories | integer | No | Estimated calories burned |
| average_speed | float | No | Average speed in m/s |
| max_speed | float | No | Maximum speed in m/s |
| average_heartrate | float | No | Average heart rate in BPM |
| max_heartrate | integer | No | Maximum heart rate in BPM |
| average_watts | float | No | Average power in watts |
| max_watts | integer | No | Maximum power in watts |
| average_cadence | float | No | Average cadence (RPM or SPM) |
| gear_id | string | No | Associated gear ID |
| device_name | string | No | Recording device name |
| trainer | boolean | No | Indoor trainer activity |
| commute | boolean | No | Commute activity |
| private | boolean | No | Private activity flag |
| kudos_count | integer | Yes | Number of kudos |
| comment_count | integer | Yes | Number of comments |
| athlete_count | integer | No | Number of athletes (group activities) |
| achievement_count | integer | No | Number of achievements |
| pr_count | integer | No | Number of personal records |

**Nested Arrays in `info.json`**:
- `comments[]`: Array of Comment objects
- `kudos[]`: Array of Kudo objects
- `laps[]`: Array of lap data
- `segment_efforts[]`: Array of segment effort data

**State Tracking**:
| Field | Type | Description |
|-------|------|-------------|
| has_gps | boolean | Activity has GPS track data |
| has_photos | boolean | Activity has photos |
| photo_count | integer | Number of photos |

---

### Track (GPS/Sensor Data)

**Description**: Time-series data for an activity including GPS coordinates and sensor streams.

**Storage**: `tracking.parquet` (Parquet format) + `tracking.json` (manifest)

**Parquet Schema**:

| Column | Type | Description |
|--------|------|-------------|
| time | float64 | Seconds from activity start |
| lat | float64 | Latitude in decimal degrees |
| lng | float64 | Longitude in decimal degrees |
| altitude | float32 | Elevation in meters |
| distance | float32 | Cumulative distance in meters |
| heartrate | int16 | Heart rate in BPM |
| cadence | int16 | Cadence (RPM or SPM) |
| watts | int16 | Power in watts |
| temp | float32 | Temperature in Celsius |
| velocity_smooth | float32 | Smoothed velocity in m/s |
| grade_smooth | float32 | Smoothed grade percentage |

**Manifest Schema** (`tracking.json`):

```json
{
  "columns": ["time", "lat", "lng", "altitude", "heartrate"],
  "row_count": 3600,
  "has_gps": true,
  "has_hr": true,
  "has_power": false
}
```

---

### Photo

**Description**: Image attached to an activity.

**Storage**: `photos/{datetime}.{ext}` where datetime is photo-specific timestamp (e.g., `20251218T144532.jpg`)

**Metadata** (stored in `info.json` photos array):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| unique_id | string | Yes | Strava photo unique ID |
| created_at | datetime | Yes | Photo timestamp |
| location | array | No | [lat, lon] if geotagged |
| urls | object | Yes | Size -> URL mapping |

---

### Comment

**Description**: Text comment on an activity from another athlete.

**Storage**: Embedded in `info.json` comments array

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | integer | Yes | Comment ID |
| text | string | Yes | Comment text |
| created_at | datetime | Yes | Comment timestamp |
| athlete_id | integer | Yes* | Commenter's athlete ID |
| athlete_firstname | string | No | Commenter's first name |
| athlete_lastname | string | No | Commenter's last name |

*Note: `athlete_id` should always be present for valid comments. May be null only if the commenter's account has been deleted or made fully private.

---

### Kudo

**Description**: A "like" on an activity from another athlete.

**Storage**: Embedded in `info.json` kudos array

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| athlete_id | integer | Yes* | Kudos giver's athlete ID |
| firstname | string | No | First name |
| lastname | string | No | Last name |

*Note: `athlete_id` should always be present for valid kudos. May be null only if the kudos giver's account has been deleted or made fully private. The code must use proper attribute access for stravalib v2 pydantic models.

---

### Gear

**Description**: Equipment (bikes, shoes) tracked by Strava.

**Storage**: `gear.json` at athlete level

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Gear ID (e.g., "b12345") |
| name | string | Yes | Gear name |
| type | string | Yes | "bike" or "shoes" |
| brand | string | No | Brand name |
| model | string | No | Model name |
| distance_m | float | Yes | Total distance in meters |
| primary | boolean | Yes | Is primary gear |
| retired | boolean | Yes | Is retired |

---

### FitTrackee Export State

**Description**: Tracks which activities have been exported to FitTrackee.

**Storage**: `exports/fittrackee.json` at athlete level

**Schema**:

```json
{
  "fittrackee_url": "https://fittrackee.example.com",
  "exports": [
    {
      "ses": "20251218T143022",
      "ft_workout_id": 12345,
      "exported_at": "2025-12-18T15:30:00Z"
    }
  ]
}
```

---

### Sport Type Mapping

**Description**: Bidirectional mapping between Strava and FitTrackee sport types.

**Storage**: Configuration file or embedded constant

**Mapping**:

| Strava Type | FitTrackee ID | FitTrackee Label |
|-------------|---------------|------------------|
| Run | 5 | Running |
| VirtualRun | 5 | Running |
| TrailRun | 5 | Running |
| Ride | 1 | Cycling (Sport) |
| VirtualRide | 1 | Cycling (Sport) |
| EBikeRide | 2 | Cycling (Transport) |
| MountainBikeRide | 4 | Mountain Biking |
| GravelRide | 1 | Cycling (Sport) |
| Hike | 3 | Hiking |
| Walk | 6 | Walking |
| Swim | - | (Not mapped - skip) |
| Other | 6 | Walking (fallback) |

---

### Sessions Summary (TSV)

**Description**: Denormalized summary of all activities for efficient querying.

**Storage**: `sessions.tsv` at athlete level

**Columns**:

| Column | Type | Description |
|--------|------|-------------|
| datetime | string | Session datetime (ISO 8601 basic) |
| type | string | Activity type |
| sport | string | Sport type |
| name | string | Activity name |
| distance_m | float | Distance in meters |
| moving_time_s | integer | Moving time in seconds |
| elapsed_time_s | integer | Elapsed time in seconds |
| elevation_gain_m | float | Elevation gain in meters |
| calories | integer | Calories burned |
| avg_hr | float | Average heart rate |
| max_hr | integer | Maximum heart rate |
| avg_watts | float | Average power |
| gear_id | string | Gear ID |
| athletes | integer | Athlete count |
| kudos_count | integer | Kudos count |
| comment_count | integer | Comment count |
| has_gps | boolean | Has GPS data |
| has_photos | boolean | Has photos |
| photo_count | integer | Photo count |

---

### Athletes Summary (TSV)

**Description**: Top-level summary of all athletes in the backup.

**Storage**: `athletes.tsv` at data directory root

**Columns**:

| Column | Type | Description |
|--------|------|-------------|
| username | string | Athlete username |
| firstname | string | First name (from profile) |
| lastname | string | Last name (from profile) |
| city | string | City (from profile) |
| country | string | Country (from profile) |
| session_count | integer | Number of activities |
| first_activity | string | Earliest activity datetime |
| last_activity | string | Latest activity datetime |
| total_distance_km | float | Total distance in km |
| total_moving_time_h | float | Total moving time in hours |
| activity_types | string | Comma-separated list of activity types |

---

## Validation Rules

### Activity
- `id` must be positive integer
- `distance` must be non-negative
- `moving_time` <= `elapsed_time`
- `start_date` must be valid ISO 8601 datetime
- `type` must be known Strava activity type

### Track
- All GPS coordinates must be valid (-90 <= lat <= 90, -180 <= lng <= 180)
- `time` values must be monotonically increasing
- Sensor values must be within physical ranges (HR: 30-250, cadence: 0-300, watts: 0-3000)

### Photo
- Filename must be valid datetime format
- Extension must be valid image type (jpg, jpeg, png)

### FitTrackee Export
- `ft_workout_id` must be positive integer
- `exported_at` must be valid ISO 8601 datetime
- `ses` must match existing activity session

---

## State Transitions

### Activity Lifecycle

```
[New on Strava] --> [Fetched] --> [Backed Up]
                         │
                         ▼
                    [Exported to FitTrackee]
```

### Sync State

The sync state is tracked implicitly:
1. Last successful sync time stored in config
2. Activities with `ses > last_sync` are new
3. `sessions.tsv` modification time indicates last sync

### Export State

```
[Not Exported] --> [Exported] --> [Re-exported (updated)]
```

Export state tracked per-activity in `exports/fittrackee.json`.
