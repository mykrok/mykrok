# Tasks: MyKrok - Fitness Activity Backup and Visualization

**Input**: Design documents from `/specs/001-mykrok/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project structure per plan.md with src/mykrok/ directory layout
- [X] T002 Initialize Python project with pyproject.toml (stravalib, PyArrow, requests, DuckDB dependencies)
- [X] T003 [P] Configure tox.ini with py3{10,11,12,13} environments, lint, and type targets
- [X] T004 [P] Configure ruff and mypy in pyproject.toml
- [X] T005 [P] Create GitHub Actions workflow for CI in .github/workflows/ci.yml
- [X] T006 Create src/mykrok/__init__.py with version and package metadata
- [X] T007 [P] Create tests/conftest.py with shared pytest fixtures
- [X] T008 [P] Create tests/fixtures/ directory with sample activity JSON and stream data

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T009 Implement configuration management in src/mykrok/config.py (TOML config, env vars)
- [X] T010 [P] Implement Hive-partitioned path helpers in src/mykrok/lib/paths.py
- [X] T011 [P] Implement Parquet utilities in src/mykrok/lib/parquet.py (schema, streaming writes)
- [X] T012 [P] Implement rate limiter wrapper in src/mykrok/services/rate_limiter.py
- [X] T013 Implement Strava API client in src/mykrok/services/strava.py (wraps stravalib, OAuth2 handling)
- [X] T014 Implement CLI entry point and global options in src/mykrok/cli.py and src/mykrok/__main__.py
- [X] T015 Implement Activity model with storage operations in src/mykrok/models/activity.py
- [X] T016 [P] Implement Athlete model in src/mykrok/models/athlete.py
- [X] T017 [P] Implement sync state tracking in src/mykrok/models/state.py
- [X] T018 Implement `mykrok auth` command for OAuth2 authentication in src/mykrok/cli.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 2b: CLI Test Infrastructure (REQUIRED)

**Purpose**: Set up CLI testing infrastructure before any command implementation.
Tests are written WITH commands, not after.

- [X] T018a Create CLI test fixtures using `generate_fixtures.py` in tests/cli/conftest.py
- [X] T018b Create `cli_data_dir` fixture with realistic athlete data (2 athletes, 10+ sessions)
- [X] T018c Create `cli_runner` fixture wrapping Click's CliRunner
- [X] T018d Create helper functions for verifying file system changes

**Checkpoint**: CLI test infrastructure ready - command tests can now be written alongside commands

---

## Phase 3: User Story 1 - Backup My Own Activities (Priority: P1)

**Goal**: Back up all Strava activities (metadata, GPS tracks, photos) with incremental sync

**Independent Test**: Run `mykrok sync` and verify activity data, GPS tracks, and photos are saved locally in the Hive-partitioned structure.

### Implementation for User Story 1

- [X] T019 [US1] Implement GPS/sensor stream handling in src/mykrok/models/tracking.py
- [X] T020 [US1] Implement GPX generation with Garmin extensions in src/mykrok/lib/gpx.py
- [X] T021 [US1] Implement backup orchestration service in src/mykrok/services/backup.py
- [X] T022 [US1] Implement incremental sync logic (after timestamp, new activities only) in src/mykrok/services/backup.py
- [X] T023 [US1] Implement photo download and storage in src/mykrok/services/backup.py
- [X] T024 [US1] Implement sessions.tsv summary generation in src/mykrok/models/activity.py
- [X] T025 [US1] Implement gear.json catalog storage in src/mykrok/models/athlete.py
- [X] T026 [US1] Implement `mykrok sync` command with all options in src/mykrok/cli.py
- [X] T027 [US1] Implement `mykrok gpx` command for GPX export in src/mykrok/cli.py
- [X] T028 [US1] Add rate limit handling and graceful pause/resume in src/mykrok/services/backup.py
- [X] T029 [US1] Handle edge cases: no GPS data, expired photo URLs, large histories

### Tests for User Story 1 (REQUIRED before checkpoint)

- [ ] T029a [US1] CLI test: `mykrok sync` creates activity files with fixture data
- [ ] T029b [US1] CLI test: `mykrok sync --dry-run` makes no file changes
- [ ] T029c [US1] CLI test: `mykrok sync --json` produces valid JSON output
- [X] T029d [US1] CLI test: `mykrok gpx` generates valid GPX files
- [X] T029e [US1] Unit test: backup.py sync orchestration logic
- [ ] T029f [US1] Unit test: strava.py API client with mocks

**Checkpoint**: User Story 1 complete - can backup activities with GPS tracks and photos
**Gate**: Tests T029a-T029f must pass; coverage of backup.py >= 50% (currently 60%)

---

## Phase 4: User Story 2 - View My Running History on a World Map (Priority: P2)

**Goal**: Interactive world map visualization showing all activity routes with heatmap mode

**Independent Test**: Generate map HTML from backed-up activities and verify routes appear in correct geographic locations with clickable details.

### Implementation for User Story 2

- [X] T030 [US2] Implement map generation service in src/mykrok/views/map.py
- [X] T031 [US2] Create Leaflet-based HTML template for route visualization (Canvas renderer)
- [X] T032 [US2] Implement heatmap mode using leaflet.heat plugin in src/mykrok/views/map.py
- [X] T033 [US2] Implement route click handler showing activity details (name, date, distance)
- [X] T034 [US2] Implement date filtering for map (--after, --before options)
- [X] T035 [US2] Implement activity type filtering for map (--type option)
- [X] T036 [US2] Implement local HTTP server for map viewing in src/mykrok/views/map.py
- [X] T037 [US2] Implement `mykrok view map` command in src/mykrok/cli.py

### Tests for User Story 2 (REQUIRED before checkpoint)

- [X] T037a [US2] CLI test: `mykrok create-browser` generates index.html and assets
- [X] T037b [US2] CLI test: `mykrok create-browser -o <dir>` respects output directory
- [ ] T037c [US2] Unit test: map.py generates valid HTML with routes

**Checkpoint**: User Story 2 complete - can visualize activities on interactive map with heatmap
**Gate**: Tests T037a-T037c must pass; coverage of map.py >= 50% (currently 63%)

---

## Phase 5: User Story 3 - Filter and View Statistics by Time Period (Priority: P3)

**Goal**: Statistics by year/month/custom range with breakdowns by activity type

**Independent Test**: Select different time periods and verify statistics are calculated correctly for the filtered set.

### Implementation for User Story 3

- [X] T038 [US3] Implement statistics calculation service in src/mykrok/views/stats.py
- [X] T039 [US3] Implement date range filtering (year, month, custom) for statistics
- [X] T040 [US3] Implement breakdown by month (--by-month option)
- [X] T041 [US3] Implement breakdown by activity type (--by-type option)
- [X] T042 [US3] Implement text and JSON output formatting for statistics
- [X] T043 [US3] Implement `mykrok view stats` command in src/mykrok/cli.py

### Tests for User Story 3 (REQUIRED before checkpoint)

- [X] T043a [US3] CLI test: `mykrok view stats` outputs correct totals
- [X] T043b [US3] CLI test: `mykrok view stats --json` produces valid JSON
- [X] T043c [US3] CLI test: `mykrok view stats --year 2025` filters correctly
- [ ] T043d [US3] Unit test: stats.py calculates correct aggregates

**Checkpoint**: User Story 3 complete - can view statistics filtered by time period
**Gate**: Tests T043a-T043d must pass; coverage of stats.py >= 50% (currently 64%)

---

## Phase 6: User Story 4 - Backup Comments from My Activities (Priority: P4)

**Goal**: Backup all comments and kudos on activities

**Independent Test**: Backup an activity with comments and verify comments are stored with author names, timestamps, and text.

### Implementation for User Story 4

- [X] T044 [US4] Extend backup service to fetch comments in src/mykrok/services/backup.py
- [X] T045 [US4] Extend backup service to fetch kudos list in src/mykrok/services/backup.py
- [X] T046 [US4] Store comments and kudos in info.json per data-model.md schema
- [X] T047 [US4] Update sessions.tsv to include kudos_count and comment_count columns
- [X] T048 [US4] Add --no-comments option to sync command for skipping social data

### Tests for User Story 4 (REQUIRED before checkpoint)

- [ ] T048a [US4] CLI test: `mykrok sync --what=social` updates social data
- [ ] T048b [US4] CLI test: `mykrok sync --no-comments` skips social data
- [ ] T048c [US4] Unit test: backup.py social data refresh logic

**Checkpoint**: User Story 4 complete - comments and kudos are backed up
**Gate**: Tests T048a-T048c must pass

---

## Phase 7: User Story 5 - Browse Activities Offline (Priority: P5)

**Goal**: Local web interface to browse backed-up activities, photos, and route details

**Independent Test**: Disconnect from internet and browse backed-up activities through local interface.

### Implementation for User Story 5

- [X] T049 [US5] Implement local activity browser service in src/mykrok/views/browser.py
- [X] T050 [US5] Create HTML template for activity list view (sorted by date)
- [X] T051 [US5] Create HTML template for activity detail view (metadata, route map, photos, comments)
- [X] T052 [US5] Implement static file serving for photos
- [X] T053 [US5] Implement route display on detail page using Leaflet
- [X] T054 [US5] Implement `mykrok browse` command in src/mykrok/cli.py

### Tests for User Story 5 (REQUIRED before checkpoint)

- [ ] T054a [US5] CLI test: `mykrok create-browser --serve` starts HTTP server
- [ ] T054b [US5] CLI test: Generated browser loads without JS errors (E2E)

**Checkpoint**: User Story 5 complete - can browse activities offline
**Gate**: Tests T054a-T054b must pass

---

## Phase 8: User Story 6 - Export to FitTrackee (Priority: P6)

**Goal**: Export activities to self-hosted FitTrackee with sport type mapping and incremental sync

**Independent Test**: Run export command against Docker-based FitTrackee and verify activities appear with proper sport types, GPS tracks, and metadata.

### Implementation for User Story 6

- [X] T055 [US6] Implement FitTrackee API client in src/mykrok/services/fittrackee.py (auth, upload)
- [X] T056 [US6] Implement sport type mapping (Strava → FitTrackee) with fallback handling
- [X] T057 [US6] Implement GPX generation with HR/cadence/power extensions for FitTrackee
- [X] T058 [US6] Implement FitTrackee export state tracking in src/mykrok/models/state.py
- [X] T059 [US6] Store export state in exports/fittrackee.json per data-model.md schema
- [X] T060 [US6] Implement incremental export (skip already-exported activities)
- [X] T061 [US6] Implement FitTrackee rate limiting (300 req/5min) in src/mykrok/services/rate_limiter.py
- [X] T062 [US6] Handle GPX file size limit (simplify large tracks if >1MB)
- [X] T063 [US6] Implement `mykrok export fittrackee` command with all options in src/mykrok/cli.py
- [X] T064 [US6] Handle edge cases: no GPS (skip), unmapped sport types (fallback + warning)

### Tests for User Story 6 (REQUIRED before checkpoint)

- [ ] T064a [US6] CLI test: `mykrok export fittrackee --dry-run` shows export plan
- [ ] T064b [US6] CLI test: `mykrok export fittrackee --json` produces valid JSON
- [X] T064c [US6] Unit test: fittrackee.py API client with mocks
- [ ] T064d [US6] Integration test: FitTrackee export via Docker (pytest-docker)

**Checkpoint**: User Story 6 complete - can export to FitTrackee with incremental sync
**Gate**: Tests T064a-T064d must pass; coverage of fittrackee.py >= 50% (currently 63%)

---

## Phase 8b: User Story 7 - DataLad Dataset Creation (Priority: P7)

**Goal**: Create a DataLad dataset for version-controlled, reproducible activity backups

**Independent Test**: Run `mykrok create-datalad-dataset ./my-activities` and verify:
- DataLad dataset is created with text2git configuration
- Sample config file with comments is generated
- README.md describing the dataset is created
- Makefile with `datalad run` sync target is generated

### Implementation for User Story 7

- [X] T077 [US7] Add datalad dependency to pyproject.toml
- [X] T078 [US7] Implement DataLad dataset creation service in src/mykrok/services/datalad.py
- [X] T079 [US7] Create template for sample .mykrok.toml config with comments
- [X] T080 [US7] Create template for dataset README.md
- [X] T081 [US7] Create template for Makefile with `datalad run` sync target
- [X] T082 [US7] Implement `mykrok create-datalad-dataset` command in src/mykrok/cli.py
- [X] T083 [US7] [P] Create unit tests for DataLad dataset creation in tests/unit/test_datalad.py
- [X] T084 [US7] Configure git-annex to add config file unlocked (annex.addunlocked) for easy editing
- [X] T085 [US7] Preserve comments when saving OAuth tokens using tomlkit
- [X] T086 [US7] Suppress spurious stravalib warnings about environment variables
- [X] T087 [US7] Fix unclosed socket warning after OAuth authentication

### Tests for User Story 7 (already implemented)

- [X] T083 [US7] [P] Create unit tests for DataLad dataset creation in tests/unit/test_datalad.py

**Checkpoint**: User Story 7 complete - can create reproducible DataLad datasets for backups
**Gate**: Test T083 passes; coverage of datalad.py >= 70%

---

## Phase 9: Coverage Gate & Cross-Cutting Concerns (REQUIRED for Release)

**Purpose**: Ensure minimum coverage and cross-cutting quality before release.
This phase is NOT optional polish - it gates releases.

### Cross-Cutting Implementation

- [X] T065 [P] Add comprehensive logging across all modules
- [X] T066 [P] Implement --json output format for all commands in src/mykrok/cli.py
- [X] T067 [P] Implement --quiet mode for cron usage
- [X] T068 [P] Implement --verbose levels for debugging
- [X] T069 Run quickstart.md validation (verify all documented commands work)
- [X] T070 [P] Add type hints and docstrings to all public functions

### Coverage Gate (REQUIRED)

- [X] T090 Verify overall coverage >= 60%: `tox -e cov` (currently 62%)
- [ ] T091 Verify CLI tests exist for all commands in contracts/cli.md
- [X] T092 Verify no service module has 0% coverage (all modules covered)
- [X] T093 Create CLI integration tests in tests/cli/ using fixture data

### Existing Tests (from earlier implementation)

- [X] T071 [P] Create integration tests for Strava API (mocked) in tests/integration/test_strava_api.py
- [X] T072 [P] Create integration tests for FitTrackee (Docker) in tests/integration/test_fittrackee.py
- [X] T073 [P] Create unit tests for models in tests/unit/test_models.py
- [X] T074 [P] Create unit tests for GPX generation in tests/unit/test_gpx.py
- [X] T075 [P] Create unit tests for backup logic in tests/unit/test_backup.py
- [X] T076 Final code review and cleanup

**Checkpoint**: Release gate passed - coverage >= 60%, all CLI commands tested
**BLOCKS**: Any release until T090-T093 complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - User stories can proceed in priority order (P1 → P2 → P3 → P4 → P5 → P6)
  - Or in parallel if staffed (US1 and US2 have no dependencies on each other)
- **Polish (Phase 9)**: Depends on desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Core backup - no dependencies on other stories
- **User Story 2 (P2)**: Depends on backed-up GPS data (US1 must be complete for real data, but can develop with fixtures)
- **User Story 3 (P3)**: Depends on backed-up data (US1 must be complete for real data, but can develop with fixtures)
- **User Story 4 (P4)**: Extends US1 backup service - can develop in parallel
- **User Story 5 (P5)**: Depends on backed-up data (US1 must be complete)
- **User Story 6 (P6)**: Depends on backed-up data and GPX generation (US1 must be complete)
- **User Story 7 (P7)**: Independent - creates dataset structure for future sync operations

### Within Each User Story

- Models before services
- Services before CLI commands
- Core implementation before edge case handling
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```bash
# Run in parallel:
Task T003: Configure tox.ini
Task T004: Configure ruff and mypy
Task T005: Create GitHub Actions workflow
Task T007: Create tests/conftest.py
Task T008: Create tests/fixtures/
```

**Phase 2 (Foundational)**:
```bash
# Run in parallel:
Task T010: Implement paths.py
Task T011: Implement parquet.py
Task T012: Implement rate_limiter.py
Task T016: Implement athlete.py
Task T017: Implement state.py
```

**User Story 1 (after models ready)**:
```bash
# T019 and T020 can run in parallel:
Task T019: Implement tracking.py
Task T020: Implement gpx.py
```

**User Story 2 (independent from US3-6)**:
```bash
# After foundational, US2 can develop with fixtures while US1 is in progress
```

**Phase 9 (Polish)**:
```bash
# All test tasks can run in parallel:
Task T071: Integration tests Strava API
Task T072: Integration tests FitTrackee
Task T073: Unit tests models
Task T074: Unit tests GPX
Task T075: Unit tests backup
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Backup)
4. **STOP and VALIDATE**: Test `mykrok auth` and `mykrok sync`
5. Deploy/demo if ready - users can now backup their Strava activities!

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test backup → **MVP Release** (core value delivered)
3. Add User Story 2 → Test map → Release (visualization added)
4. Add User Story 3 → Test stats → Release (analytics added)
5. Add User Story 4 → Test comments → Release (social data added)
6. Add User Story 5 → Test browser → Release (offline access added)
7. Add User Story 6 → Test FitTrackee → Release (export capability added)
8. Each story adds value without breaking previous stories

### Recommended Order for Solo Developer

1. Phase 1: Setup (T001-T008)
2. Phase 2: Foundational (T009-T018)
3. Phase 3: User Story 1 - Backup (T019-T029) ← **MVP milestone**
4. Phase 4: User Story 2 - Map (T030-T037)
5. Phase 5: User Story 3 - Stats (T038-T043)
6. Phase 6: User Story 4 - Comments (T044-T048)
7. Phase 7: User Story 5 - Browser (T049-T054)
8. Phase 8: User Story 6 - FitTrackee (T055-T064)
9. Phase 9: Polish (T065-T076)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
