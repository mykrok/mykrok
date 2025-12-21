# Feature Specification: Strava Activity Backup and Visualization

**Feature Branch**: `001-strava-backup`
**Created**: 2025-12-18
**Status**: Draft
**Input**: User description: "Backup and keep updating a full collection of posts from me and people I follow on Strava. Capture photos, tracks, comments. Provide worldmap view rendering (points/flags or heatmap) showing where I have run, with stats by year/month."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Backup My Own Activities (Priority: P1)

As an athlete, I want to back up all my own Strava activities (runs, rides, etc.) including the GPS tracks, photos, and metadata so that I have a local archive independent of Strava's service.

**Why this priority**: This is the core functionality. Having my own activity data is the foundation for everything else - visualizations, statistics, and independence from the Strava platform.

**Independent Test**: Can be fully tested by running a backup command and verifying that activity data, GPS tracks, and photos are saved locally in a browsable format.

**Acceptance Scenarios**:

1. **Given** I have authenticated with Strava, **When** I run an initial backup, **Then** all my activities are downloaded with their metadata (title, description, distance, duration, elevation, type), GPS tracks, and photos.
2. **Given** I have an existing backup, **When** I run an incremental backup after uploading new activities to Strava, **Then** only new activities are downloaded (no duplicate downloads).
3. **Given** an activity has photos attached, **When** the activity is backed up, **Then** all photos are downloaded in their original resolution.
4. **Given** an activity has GPS data, **When** the activity is backed up, **Then** the route is saved in a standard format (GPX) that can be imported into other tools.

---

### User Story 2 - View My Running History on a World Map (Priority: P2)

As an athlete, I want to view all my activities plotted on an interactive world map, showing where I have run/cycled over time, so I can visualize my athletic journey geographically.

**Why this priority**: This provides immediate value from the backed-up data and is a key differentiator from simply downloading files - it enables discovery and reflection on one's athletic history.

**Independent Test**: Can be fully tested by generating a map view from backed-up activities and verifying routes appear in correct geographic locations.

**Acceptance Scenarios**:

1. **Given** I have backed-up activities with GPS data, **When** I open the map view, **Then** I see all my routes displayed on an interactive map.
2. **Given** I have activities from multiple locations (cities, countries), **When** I view the map, **Then** I can zoom/pan to see activities in different regions.
3. **Given** I want to see activity patterns, **When** I enable heatmap mode, **Then** frequently-run routes appear more prominently than one-time routes.
4. **Given** I click on a route on the map, **When** the route details appear, **Then** I can see the activity name, date, distance, and a link to view full details.

---

### User Story 3 - Filter and View Statistics by Time Period (Priority: P3)

As an athlete, I want to filter my activities and statistics by year, month, or custom date range, so I can track my progress over time and compare different training periods.

**Why this priority**: Statistics and filtering enhance the usefulness of the backup by providing insights. This builds on the map visualization to provide quantitative analysis.

**Independent Test**: Can be fully tested by selecting different time periods and verifying statistics are calculated correctly for the filtered set.

**Acceptance Scenarios**:

1. **Given** I have multiple years of activities, **When** I filter to a specific year, **Then** only activities from that year appear on the map and in statistics.
2. **Given** I filter to a specific month, **When** I view statistics, **Then** I see totals for distance, time, elevation gain, and activity count for that month.
3. **Given** I want to compare months, **When** I view yearly statistics, **Then** I can see a breakdown by month showing trends in my training volume.

---

### User Story 4 - Backup Comments from My Activities (Priority: P4)

As an athlete, I want to back up all comments on my activities so I can preserve the social interactions and feedback from my Strava community.

**Why this priority**: Comments are valuable social context but secondary to the core activity data. They enhance the backup completeness.

**Independent Test**: Can be fully tested by backing up an activity with comments and verifying comments are stored with author names, timestamps, and text.

**Acceptance Scenarios**:

1. **Given** an activity has comments, **When** the activity is backed up, **Then** all comments are saved including commenter name, timestamp, and comment text.
2. **Given** an activity has kudos, **When** the activity is backed up, **Then** the kudos count and list of athletes who gave kudos are saved.

---

### User Story 5 - Browse Activities Offline (Priority: P5)

As an athlete, I want to browse my backed-up activities locally without needing the Strava app or website, including viewing photos and route details.

**Why this priority**: Provides value from the backup beyond just archival - enables offline access and independence from Strava's platform.

**Independent Test**: Can be fully tested by disconnecting from the internet and browsing backed-up activities through a local interface.

**Acceptance Scenarios**:

1. **Given** I have backed-up activities, **When** I open the local viewer, **Then** I can browse activities sorted by date with their titles, types, and basic stats visible.
2. **Given** I select a specific activity, **When** I view its details, **Then** I see all metadata, the route map, photos, and comments.
3. **Given** I want to access the backup offline, **When** I open the viewer without internet, **Then** all locally-stored data is accessible (map tiles may require pre-caching or show a basic route outline).

---

### User Story 6 - Export to FitTrackee (Priority: P6)

As an athlete, I want to export my backed-up activities to a self-hosted FitTrackee instance, so I can maintain an independent copy of my fitness data with full ownership and use FitTrackee's features for analysis and visualization.

**Why this priority**: Provides data portability to another self-hosted platform. Builds on the existing backup data model to enable export without re-fetching from Strava.

**Independent Test**: Can be fully tested by running an export command against a local FitTrackee instance (using Docker) and verifying activities appear correctly in FitTrackee with proper sport types, GPS tracks, and metadata.

**Acceptance Scenarios**:

1. **Given** I have backed-up activities with GPS data, **When** I run the FitTrackee export command with valid FitTrackee credentials, **Then** activities are uploaded to FitTrackee with correct sport type mapping.
2. **Given** an activity has GPS and sensor data (heart rate, cadence, power), **When** the activity is exported, **Then** all available sensor streams are included in the GPX file uploaded to FitTrackee.
3. **Given** I have already exported some activities, **When** I run the export again, **Then** only new activities are exported (no duplicates created in FitTrackee).
4. **Given** an activity has a title and description, **When** exported to FitTrackee, **Then** the title (max 255 chars) and notes (max 500 chars) are preserved.
5. **Given** an activity's Strava sport type has no direct FitTrackee equivalent, **When** exported, **Then** a sensible fallback sport type is used and a warning is logged.
6. **Given** the FitTrackee API returns an error during export, **When** the error occurs, **Then** it is logged with details and export continues with remaining activities.

---

### Edge Cases

- What happens when an activity has no GPS data (e.g., treadmill runs, manual entries)?
  - Activity metadata and photos are still backed up; map view shows activity in list but not on map.
  - For FitTrackee export: Activity is skipped (FitTrackee requires GPX for outdoor activities); warning logged.
- What happens when Strava API rate limits are hit during backup?
  - Backup pauses and resumes automatically when rate limit resets; progress is saved so no re-downloading occurs.
- What happens when a photo URL expires or becomes unavailable?
  - Error is logged; backup continues with other content; missing photos are noted for retry.
- What happens when the user has thousands of activities?
  - Backup runs incrementally; only fetches new/modified activities after initial sync.
- What happens when Strava authentication token expires?
  - User is prompted to re-authenticate; backup resumes from where it left off.
- What happens when FitTrackee API rate limit is hit (default 300 req/5 min)?
  - Export pauses and resumes automatically; progress tracked to avoid re-uploading.
- What happens when FitTrackee file size limit (1MB) is exceeded?
  - Large GPX files are simplified (reduced point density) before upload; original preserved locally.
- What happens when FitTrackee authentication fails during export?
  - User is prompted with clear error message to verify FitTrackee URL and API token.

## Clarifications

### Session 2025-12-18

- Q: FitTrackee integration scope → A: Export from local backup to FitTrackee via REST API; GPX upload with sport mapping; integration tests via Docker
- Q: Incremental updates efficiency → A: Daily runs expected; must efficiently fetch updates without refetching entire history
- Q: Architecture pattern → A: MVC model with clear separation of model (stored files, layout), view (stats, visualizations), and efficient controller for incremental view updates
- Q: Athlete filtering → A: Regex-based exclusion patterns for athletes to skip during backup
- Q: Strava API library → A: Use stravalib (https://github.com/stravalib/stravalib) for Strava API interactions
- Q: File storage structure → A: Hive-partitioned layout for DuckDB compatibility: `athl={username}/ses={datetime}/` with parquet files for queryable data
- Q: Session datetime format → A: ISO 8601 basic format without special characters: `ses=20251218T143022`
- Q: Time-series data storage → A: Single `tracking.parquet` file with all streams (GPS, HR, cadence, power, etc.) plus `tracking.json` manifest describing available columns
- Q: Sessions summary content → A: Comprehensive TSV with datetime, type, sport, name, distance_m, moving_time_s, elapsed_time_s, elevation_gain_m, calories, avg_hr, max_hr, avg_watts, gear_id, athletes, kudos_count, comment_count, has_gps, has_photos, photo_count
- Q: Photo naming convention → A: Photo-specific timestamp from Strava metadata: `20251218T144532.jpg`
- Q: Gear catalog storage → A: Athlete-level `gear.json` with id, name, type, brand, model, distance_m, primary, retired

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate with Strava using OAuth2 and securely store refresh tokens for ongoing access.
- **FR-002**: System MUST download all activities for the authenticated athlete including metadata (title, description, type, sport type, distance, moving time, elapsed time, elevation gain, start date, start location).
- **FR-003**: System MUST download GPS and sensor stream data for each activity and store it in `tracking.parquet` format with a `tracking.json` manifest describing available columns. GPX export is supported for interoperability.
- **FR-004**: System MUST download all photos attached to activities in their highest available resolution.
- **FR-005**: System MUST download comments and kudos for each activity.
- **FR-006**: System MUST perform incremental backups, only fetching activities newer than the last backup. Designed for daily execution with minimal API calls and no re-downloading of existing data.
- **FR-007**: System MUST respect Strava API rate limits (200 requests per 15 minutes, 2000 per day) and handle rate limiting gracefully.
- **FR-008**: System MUST store backed-up data in a Hive-partitioned directory structure (`athl={username}/ses={datetime}/`) with JSON for metadata, Parquet for time-series data, and TSV for session summaries. This enables both human browsing and efficient DuckDB queries.
- **FR-009**: System MUST generate an interactive map visualization showing all backed-up activities with GPS data.
- **FR-010**: System MUST support heatmap visualization mode to show frequently-traveled routes.
- **FR-011**: System MUST allow filtering activities by date range (year, month, custom range).
- **FR-012**: System MUST calculate and display statistics (total distance, time, elevation, count) for filtered activity sets.
- **FR-013**: System MUST provide an offline-capable interface to browse backed-up activities, photos, and route maps.
- **FR-014**: System MUST support athlete exclusion via regex patterns to skip specific athletes during backup operations.
- **FR-015**: Controller MUST efficiently update views incrementally based on model changes, avoiding full re-rendering of statistics and visualizations when only partial updates are needed.
- **FR-016**: System MUST maintain a `sessions.tsv` summary file at the athlete level, updated after each sync with comprehensive activity metrics.
- **FR-017**: System MUST maintain a `gear.json` catalog at the athlete level with equipment details (id, name, type, brand, model, distance, primary, retired status).
- **FR-018**: System MUST support export to FitTrackee via its REST API, uploading GPX files with sport type mapping and metadata.
- **FR-019**: System MUST maintain a Strava-to-FitTrackee sport type mapping configuration (Running→5, Cycling→1, Hiking→3, etc.) with fallback handling for unmapped types.
- **FR-020**: System MUST track export state per activity to enable incremental exports (no duplicate uploads to FitTrackee).
- **FR-021**: System MUST generate GPX files with extended data (heart rate, cadence, power) when available in tracking data for FitTrackee upload.
- **FR-022**: System MUST respect FitTrackee API rate limits (default 300 requests per 5 minutes) with automatic pause and resume.
- **FR-023**: System MUST provide integration tests for FitTrackee export using a Docker-based FitTrackee instance.
- **FR-024**: *(Implemented)* Map view supports URL permalinks that encode view state including: map center coordinates, zoom level, selected session/popup, visible layers, and active filters. This enables bookmarking specific views and preserving state across page reloads.

### Key Entities

- **Activity**: An athletic activity with metadata (name, type, sport, distance, duration, elevation, date), associated GPS track, photos, comments, and kudos.
- **GPS Track**: Geographic coordinate stream including latitude, longitude, altitude, and timestamps for an activity.
- **Photo**: Image file associated with an activity, including metadata (timestamp, location if available).
- **Comment**: Text feedback on an activity with author information and timestamp.
- **Athlete**: The authenticated user whose data is being backed up; includes profile information. Subject to exclusion filtering via regex patterns.
- **Exclusion Pattern**: A regex pattern used to filter out athletes by name or ID during backup operations.
- **Statistics**: Aggregated metrics (distance, time, elevation, count) calculated from a set of activities.
- **Gear**: Equipment (bikes, shoes) tracked by Strava with cumulative distance and lifecycle status.
- **FitTrackee Export State**: Tracks which activities have been exported to FitTrackee, including FitTrackee workout ID and export timestamp.
- **Sport Type Mapping**: Bidirectional mapping between Strava sport types and FitTrackee sport IDs.

### Data Model - File Structure

The model layer uses a **Hive-partitioned directory layout** optimized for DuckDB queries:

```
data/
└── athl={username}/                   # Athlete partition (Strava username)
    ├── sessions.tsv                   # Summary of all sessions for this athlete
    ├── gear.json                      # Gear catalog: [{id, name, type, brand, model, distance_m, primary, retired}]
    ├── exports/                       # Export state tracking
    │   └── fittrackee.json            # FitTrackee export state: {url, exports: [{ses, ft_workout_id, exported_at}]}
    └── ses={datetime}/                # Session partition (ISO 8601 basic: 20251218T143022)
        ├── info.json                  # Activity metadata, comments, kudos, laps, segment efforts
        ├── tracking.parquet           # All time-series streams in columnar format
        ├── tracking.json              # Manifest: {columns: ["time", "lat", "lng", ...], row_count: N}
        └── photos/                    # Activity photos
            └── {datetime}.{ext}       # Photo timestamp from Strava metadata: 20251218T144532.jpg
```

**`info.json` contents**:
- Core: id, name, description, type, sport_type, start_date, timezone
- Metrics: distance, moving_time, elapsed_time, total_elevation_gain, calories
- Performance: average_speed, max_speed, average_heartrate, max_heartrate, average_watts, max_watts, average_cadence
- Context: gear_id, device_name, trainer, commute, private
- Social: kudos_count, comment_count, athlete_count, achievement_count, pr_count
- Nested: comments[], kudos[], laps[], segment_efforts[]

**`tracking.parquet` columns** (as available per activity):
- time (seconds from start), lat, lng, altitude, distance
- heartrate, cadence, watts, temp, velocity_smooth, grade_smooth

**`sessions.tsv` columns**:
datetime, type, sport, name, distance_m, moving_time_s, elapsed_time_s, elevation_gain_m, calories, avg_hr, max_hr, avg_watts, gear_id, athletes, kudos_count, comment_count, has_gps, has_photos, photo_count, start_lat, start_lng

**Example DuckDB queries**:
```sql
-- Query all GPS tracks with Hive partitioning
SELECT sub, ses, lat, lng, heartrate
FROM read_parquet('data/**/tracking.parquet', hive_partitioning=true)
WHERE heartrate > 160;

-- Aggregate stats from sessions summary
SELECT sport, SUM(distance_m)/1000 as total_km, COUNT(*) as sessions
FROM read_csv_auto('data/athl=*/sessions.tsv')
GROUP BY sport;
```

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete initial backup of up to 1000 activities within the Strava daily API limit (may span multiple days for larger archives).
- **SC-002**: Incremental backup of new activities completes within 5 minutes for users with fewer than 50 new activities.
- **SC-003**: 100% of activity metadata and GPS tracks are successfully backed up (where GPS data exists).
- **SC-004**: 100% of activity photos are downloaded in their original resolution (where photos exist).
- **SC-005**: Map visualization loads and displays all routes within 10 seconds for up to 1000 activities.
- **SC-006**: Statistics calculations match Strava's own totals within 1% accuracy for distance and time metrics.
- **SC-007**: Backed-up data remains accessible and browsable without internet connectivity.
- **SC-008**: Users can filter and view activities from any specific month within 2 seconds.
- **SC-009**: FitTrackee export correctly maps 95%+ of common Strava sport types to FitTrackee equivalents.
- **SC-010**: FitTrackee integration tests pass against a Docker-based FitTrackee instance, verifying upload, sport mapping, and incremental export.
- **SC-011**: Exported activities appear in FitTrackee with GPS tracks, sensor data (where available), and metadata preserved.

### Architecture

The system follows an **MVC (Model-View-Controller)** pattern with clear separation of concerns:

- **Model**: File-based storage layer managing backed-up data (activities, GPS tracks, photos, comments). Structured directory layout with JSON metadata and binary assets. Maintains sync state for incremental updates.
- **View**: All presentation layers including HTML statistics pages, interactive maps, heatmaps, and activity detail views. Views are generated/updated only when underlying model data changes.
- **Controller**: Orchestrates data flow between Strava API and local model. Handles incremental sync logic, tracks which views need regeneration based on model changes, and coordinates efficient partial updates rather than full rebuilds.

### Technical Constraints

- **TC-001**: System MUST use `stravalib` Python library (https://github.com/stravalib/stravalib) for all Strava API interactions.
- **TC-002**: Model layer MUST track modification timestamps to enable efficient incremental view updates.
- **TC-003**: Controller MUST maintain a change manifest indicating which activities were added/modified during sync, enabling targeted view regeneration.
- **TC-004**: File structure MUST follow Hive partitioning conventions (`key=value/` directories) for native DuckDB compatibility via `read_parquet('data/**/tracking.parquet', hive_partitioning=true)`.
- **TC-005**: Parquet files MUST use PyArrow for generation to ensure broad compatibility with analysis tools.
- **TC-006**: FitTrackee export MUST use the `requests` library for REST API calls with proper OAuth2 token handling.
- **TC-007**: FitTrackee integration tests MUST use `pytest-docker` or similar to spin up a FitTrackee instance for testing.

## Assumptions

- User has a Strava account with activities to back up.
- User will register a Strava API application to obtain client credentials (this is required by Strava's API terms).
- Strava API endpoints and rate limits remain stable per current documentation.
- User accepts that backing up activities from followed athletes is not possible via the API (Strava restricts this).
- Photos are stored on CloudFront CDN with URLs that may expire; backup captures photos at time of sync.
- Map visualization will use open-source map tiles (e.g., OpenStreetMap) to avoid dependency on proprietary services.
- For FitTrackee export: User has a running FitTrackee instance (self-hosted) with API access enabled.
- FitTrackee API follows documented behavior (v1.0.x); significant API changes may require updates.

## Scope Boundaries

### In Scope
- Backup of authenticated user's own activities, GPS data, photos, comments, kudos
- Interactive map visualization with heatmap mode
- Statistics by time period
- Offline browsing of backed-up data
- GPX export of routes
- Export to FitTrackee (self-hosted workout tracker) with sport type mapping and incremental sync
- Integration tests for FitTrackee export using Docker-based FitTrackee instance

### Out of Scope
- Backup of activities from followed athletes (API limitation - see TODO below)
- Backup of club activities with full athlete identification (API limitation)
- Real-time sync with Strava (batch backup model only)
- Upload/sync back to Strava
- Social features (commenting, giving kudos through this tool)
- Mobile app version (command-line and local web interface only)

---

## Open Questions / TODO

### 1. CLI Refactoring - Deprecate Duplicate Functionality

**Status**: TODO
**Priority**: High

**Context**: The codebase has accumulated multiple ways to achieve similar functionality. With the unified web UI (lightweight SPA), some commands are now redundant.

**Items to consolidate/remove**:

1. **Remove `browse` command**: The lightweight web UI (`view map --lightweight`) now provides comprehensive browsing with sessions list, stats dashboard, and map view. The separate `browse` command duplicates this functionality.

2. **Rename/consolidate map commands**:
   - `view map --lightweight` should become a standalone command like `create-frontend` or `generate-webapp`
   - The non-lightweight `view map` (which embeds all data in HTML) may be deprecated or kept as `--embedded` variant
   - Consider: `strava-backup frontend generate` / `strava-backup frontend serve`

3. **Review `view stats`**: Stats are now in the web UI - decide if CLI stats output is still valuable (likely yes for scripting/quick checks)

**Action items**:
- Audit all CLI commands for overlap
- Mark deprecated commands with warnings before removal
- Update documentation and README
- Bump major version for breaking changes

---

### 2. Release Automation with intuit-auto

**Status**: TODO
**Priority**: Medium

**Context**: Manual releases are error-prone. Automate using intuit-auto like other projects.

**References**:
- [duct release workflow](https://github.com/con/duct/blob/main/.github/workflows/release.yml)
- [duct labels workflow](https://github.com/con/duct/blob/main/.github/workflows/labels.yaml)
- [duct .autorc](https://github.com/con/duct/blob/main/.autorc)
- [dandi-cli release workflow](https://github.com/dandi/dandi-cli/blob/master/.github/workflows/release.yml) - includes `workflow_dispatch` handling

**Action items**:
1. Add `.autorc` configuration
2. Add `labels.yaml` GitHub Action for PR labeling
3. Add `release.yml` GitHub Action with:
   - Automatic changelog generation
   - Version bumping based on PR labels
   - PyPI publishing
   - GitHub release creation
   - `workflow_dispatch` trigger for manual releases
4. Set up required GitHub secrets (PyPI token, etc.)
5. Document release process in CONTRIBUTING.md

---

### 3. Multi-Athlete Aggregation

**Status**: Postponed
**Priority**: Low

**Context**: The Strava API does not provide endpoints to access followed athletes' activities ([API Reference](https://developers.strava.com/docs/reference/)). The `GET /athlete/activities` endpoint only returns activities for the authenticated athlete. Each athlete must separately OAuth-authorize the application to access their data ([Community discussion](https://communityhub.strava.com/t5/developer-discussions/how-to-pull-activity-information-from-all-athletes-via-api/m-p/14208)).

**Problem**: Users want to view aggregated data from multiple athletes (e.g., family members, training partners) in a single map/stats view.

**Options to evaluate**:
1. **Merge tool**: Provide CLI command to merge multiple `athl={username}/` directories from separate backups into a combined dataset
2. **Multi-account auth**: Support authenticating multiple Strava accounts in a single config, syncing each to its own partition
3. **Import from shared storage**: Allow pointing to remote/shared athlete directories for read-only aggregation
4. **Stay single-athlete**: Keep current design, document manual aggregation via filesystem

**Decision**: TBD - revisit after higher priority items complete
