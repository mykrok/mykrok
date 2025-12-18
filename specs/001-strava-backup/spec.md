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

### Edge Cases

- What happens when an activity has no GPS data (e.g., treadmill runs, manual entries)?
  - Activity metadata and photos are still backed up; map view shows activity in list but not on map.
- What happens when Strava API rate limits are hit during backup?
  - Backup pauses and resumes automatically when rate limit resets; progress is saved so no re-downloading occurs.
- What happens when a photo URL expires or becomes unavailable?
  - Error is logged; backup continues with other content; missing photos are noted for retry.
- What happens when the user has thousands of activities?
  - Backup runs incrementally; only fetches new/modified activities after initial sync.
- What happens when Strava authentication token expires?
  - User is prompted to re-authenticate; backup resumes from where it left off.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate with Strava using OAuth2 and securely store refresh tokens for ongoing access.
- **FR-002**: System MUST download all activities for the authenticated athlete including metadata (title, description, type, sport type, distance, moving time, elapsed time, elevation gain, start date, start location).
- **FR-003**: System MUST download GPS stream data for each activity and export it as GPX files.
- **FR-004**: System MUST download all photos attached to activities in their highest available resolution.
- **FR-005**: System MUST download comments and kudos for each activity.
- **FR-006**: System MUST perform incremental backups, only fetching activities newer than the last backup.
- **FR-007**: System MUST respect Strava API rate limits (200 requests per 15 minutes, 2000 per day) and handle rate limiting gracefully.
- **FR-008**: System MUST store backed-up data in a structured, human-readable format that can be browsed without special tools.
- **FR-009**: System MUST generate an interactive map visualization showing all backed-up activities with GPS data.
- **FR-010**: System MUST support heatmap visualization mode to show frequently-traveled routes.
- **FR-011**: System MUST allow filtering activities by date range (year, month, custom range).
- **FR-012**: System MUST calculate and display statistics (total distance, time, elevation, count) for filtered activity sets.
- **FR-013**: System MUST provide an offline-capable interface to browse backed-up activities, photos, and route maps.

### Key Entities

- **Activity**: An athletic activity with metadata (name, type, sport, distance, duration, elevation, date), associated GPS track, photos, comments, and kudos.
- **GPS Track**: Geographic coordinate stream including latitude, longitude, altitude, and timestamps for an activity.
- **Photo**: Image file associated with an activity, including metadata (timestamp, location if available).
- **Comment**: Text feedback on an activity with author information and timestamp.
- **Athlete**: The authenticated user whose data is being backed up; includes profile information.
- **Statistics**: Aggregated metrics (distance, time, elevation, count) calculated from a set of activities.

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

## Assumptions

- User has a Strava account with activities to back up.
- User will register a Strava API application to obtain client credentials (this is required by Strava's API terms).
- Strava API endpoints and rate limits remain stable per current documentation.
- User accepts that backing up activities from followed athletes is not possible via the API (Strava restricts this).
- Photos are stored on CloudFront CDN with URLs that may expire; backup captures photos at time of sync.
- Map visualization will use open-source map tiles (e.g., OpenStreetMap) to avoid dependency on proprietary services.

## Scope Boundaries

### In Scope
- Backup of authenticated user's own activities, GPS data, photos, comments, kudos
- Interactive map visualization with heatmap mode
- Statistics by time period
- Offline browsing of backed-up data
- GPX export of routes

### Out of Scope
- Backup of activities from followed athletes (API limitation)
- Backup of club activities with full athlete identification (API limitation)
- Real-time sync with Strava (batch backup model only)
- Upload/sync back to Strava
- Social features (commenting, giving kudos through this tool)
- Mobile app version (command-line and local web interface only)
