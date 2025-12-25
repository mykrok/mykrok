# Research: MyKrok - Fitness Activity Backup and Visualization

**Branch**: `001-mykrok` | **Date**: 2025-12-18

## 1. Strava API via stravalib

### Decision: Use stravalib with automatic token refresh and built-in rate limiting

### Rationale
- Mature library (v2.4, June 2025) with comprehensive Strava API coverage
- Built-in OAuth2 token refresh handling
- Built-in rate limiting with configurable priority levels
- Returns typed model objects with BatchedResultsIterator for pagination

### Alternatives Considered
- Direct HTTP requests: More work, no rate limiting, no pagination handling
- Other libraries: stravalib is the de facto standard for Python/Strava

### Key Patterns

**OAuth2 Token Management**:
```python
from stravalib import Client

client = Client(
    access_token=token_data["access_token"],
    refresh_token=token_data["refresh_token"],
    token_expires_at=token_data["expires_at"]
)
# Client handles refresh automatically when needed
```

**Rate Limiting**:
```python
from stravalib.util.limiter import DefaultRateLimiter

client = Client(
    access_token=my_token,
    rate_limiter=DefaultRateLimiter(priority='medium')  # Throttles to stay under 15-min limit
)
```

**Incremental Activity Fetching**:
```python
# Fetch activities after last sync timestamp
activities = client.get_activities(after=last_sync_timestamp)
for activity in activities:  # BatchedResultsIterator handles pagination (200 per page)
    process_activity(activity)
```

**Activity Streams**:
```python
types = ['time', 'latlng', 'distance', 'altitude', 'heartrate', 'cadence', 'watts']
streams = client.get_activity_streams(activity_id, types=types, resolution='medium')
# Returns dict with stream_type -> EntityCollection mapping
```

**Photo Retrieval**:
```python
photos = client.get_activity_photos(activity_id, size=2048)
for photo in photos:
    download_url = photo.urls['2048']  # or appropriate size key
```

### Rate Limits (Strava)
- 600 requests per 15 minutes
- 30,000 requests per day
- stravalib's DefaultRateLimiter with `priority='medium'` handles this automatically

---

## 2. PyArrow Parquet for Time-Series Storage

### Decision: Use PyArrow with streaming writes and Hive partitioning

### Rationale
- Standard format for columnar time-series data
- Native DuckDB compatibility with `hive_partitioning=true`
- Streaming/batched writes for bounded memory usage
- Snappy compression for optimal query performance

### Alternatives Considered
- CSV: No columnar benefits, poor for large datasets
- SQLite: More complex, overkill for append-mostly workload
- HDF5: Less tooling support, proprietary feel

### Key Patterns

**Schema for Tracking Data**:
```python
import pyarrow as pa

tracking_schema = pa.schema([
    ('time', pa.float64()),      # Seconds from activity start
    ('lat', pa.float64()),       # GPS latitude
    ('lng', pa.float64()),       # GPS longitude
    ('altitude', pa.float32()),  # Elevation in meters
    ('distance', pa.float32()),  # Cumulative distance in meters
    ('heartrate', pa.int16()),   # Beats per minute
    ('cadence', pa.int16()),     # Revolutions per minute
    ('watts', pa.int16()),       # Power in watts
    ('temp', pa.float32()),      # Temperature
    ('velocity_smooth', pa.float32()),
    ('grade_smooth', pa.float32())
])
```

**Writing with DuckDB Optimization**:
```python
import pyarrow.parquet as pq

pq.write_table(
    table,
    'tracking.parquet',
    compression='snappy',    # Best for query performance
    use_dictionary=True,     # Efficient for repeated values
    row_group_size=10000,    # Good for mixed workloads
    version='2.6'            # Full feature support
)
```

**DuckDB Queries on Hive-Partitioned Data**:
```sql
SELECT sub, ses, lat, lng, heartrate
FROM read_parquet('data/**/tracking.parquet', hive_partitioning=true)
WHERE heartrate > 160;
```

### Memory Considerations
- Use `ParquetWriter` for streaming writes (bounded memory)
- Process activities in batches of 100 for large archives
- DuckDB can handle larger-than-memory datasets via streaming

---

## 3. FitTrackee REST API

### Decision: Use Bearer token auth, multipart upload, Garmin GPX extensions

### Rationale
- Well-documented REST API
- Standard OAuth 2.0 Bearer token authentication
- Supports GPX with Garmin TrackPoint extensions for HR/cadence/power

### Alternatives Considered
- Direct database import: Would bypass FitTrackee's processing, fragile
- No export feature: Users requested it

### Key Patterns

**Authentication**:
```python
# Login to get Bearer token
response = requests.post(f"{fittrackee_url}/api/auth/login", json={
    "email": email,
    "password": password
})
token = response.json()["auth_token"]

# Use in subsequent requests
headers = {"Authorization": f"Bearer {token}"}
```

**Sport Type Mapping**:
| FitTrackee ID | Label | Strava Equivalent |
|---------------|-------|-------------------|
| 1 | Cycling (Sport) | Ride, VirtualRide |
| 2 | Cycling (Transport) | EBikeRide |
| 3 | Hiking | Hike |
| 4 | Mountain Biking | MountainBikeRide |
| 5 | Running | Run, VirtualRun |
| 6 | Walking | Walk |

**GPX Upload**:
```python
files = {'file': ('activity.gpx', gpx_content, 'application/gpx+xml')}
data = {'data': json.dumps({
    'sport_id': sport_id,
    'title': title[:255],      # Max 255 chars
    'notes': notes[:500]       # Max 500 chars
})}
response = requests.post(
    f"{fittrackee_url}/api/workouts",
    headers=headers,
    files=files,
    data=data
)
```

**GPX with Garmin Extensions** (for HR, cadence, power):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
  <trk>
    <trkseg>
      <trkpt lat="40.674306" lon="-73.504532">
        <ele>7.8</ele>
        <time>2025-12-18T06:30:00Z</time>
        <extensions>
          <gpxtpx:TrackPointExtension>
            <gpxtpx:hr>145</gpxtpx:hr>
            <gpxtpx:cad>85</gpxtpx:cad>
          </gpxtpx:TrackPointExtension>
        </extensions>
      </trkpt>
    </trkseg>
  </trk>
</gpx>
```

### FitTrackee Limits
- Single file: 1 MB (default)
- ZIP archive: 10 MB (default)
- Files per ZIP: 10
- No explicit request rate limiting documented

---

## 4. Leaflet.js Map Visualization

### Decision: Use Leaflet with Canvas renderer, heatmap plugin, optional tile caching

### Rationale
- Lightweight, well-documented mapping library
- Canvas renderer handles thousands of polylines
- leaflet.heat plugin for activity density visualization
- OpenStreetMap tiles are free and FOSS-compatible

### Alternatives Considered
- Mapbox GL JS: More features but requires API key, less FOSS-aligned
- Google Maps: Proprietary, API costs
- deck.gl: Overkill for this use case

### Key Patterns

**Performance Optimizations**:
```javascript
var map = L.map('map', {
    preferCanvas: true  // Canvas renderer for better performance with many polylines
});
```

**Heatmap Layer**:
```javascript
var heat = L.heatLayer(points, {
    radius: 25,
    blur: 15,
    maxZoom: 17,
    gradient: {0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}
}).addTo(map);
```

**OpenStreetMap Tiles with Attribution**:
```javascript
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
```

**Optional Offline Caching** (using PouchDB):
```javascript
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    useCache: true,
    crossOrigin: true
}).addTo(map);
```

### Performance Best Practices
1. Use Canvas renderer for 1000+ polylines
2. Simplify GPS tracks at lower zoom levels
3. Lazy load routes (only display in current viewport)
4. Use heatmaps instead of individual polylines for overview

---

## Summary of Technical Decisions

| Area | Decision | Key Library/Tool |
|------|----------|------------------|
| Strava API | stravalib with auto-refresh and rate limiting | stravalib 2.4+ |
| Time-series storage | Parquet with Hive partitioning | PyArrow |
| Querying | DuckDB for SQL analytics | duckdb |
| FitTrackee export | REST API with GPX + Garmin extensions | requests |
| Map visualization | Leaflet with Canvas + heatmap plugin | Leaflet 1.9+ |
| GPX generation | Custom with Garmin TrackPoint extensions | xml.etree |

All decisions align with constitution principles:
- Simplicity: Standard tools and formats
- CLI-native: All operations scriptable
- FOSS: All dependencies Apache-2.0 or similar
- Efficiency: Incremental sync, rate limiting, bounded memory
- Quality: Testing via pytest, Docker for integration tests
