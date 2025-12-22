# Changelog

## v0.5.0 (2025-12-22)

#### 🚀 Features

- Add clickable legend filtering for activity types on map
- Add Layers control with heatmap toggle
- Add resizable Activities panel with drag handle
- Add date navigation buttons (prev/next day) in filter bar

#### 🔧 Improvements

- Unify FilterBar component across all 3 views (Map, Sessions, Stats) - DRY refactor
- Improve Activities panel UX: scroll preservation, resize support, touchpad compatibility
- Improve zoom animation and map interaction
- Point README.md to gh-pages demo site

#### 🐛 Bug Fixes

- Fix Stats view crash when charts have no data
- Fix heatmap stability issues

#### 📝 Documentation

- Add CHANGELOG.md in Intuit Auto format

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.4.0 (2025-12-22)

#### 🚀 Features

- Add check-and-fix sync mode (`--what=check-and-fix`) to verify data integrity and repair missing photos/tracking data
- Detect related sessions (same activity from different devices) and automatically cross-link photos between them
- Add `related_sessions` field to activity metadata for session cross-referencing
- Add pre-commit hooks (ruff, mypy, codespell)

#### 🔧 Improvements

- Better reporting in check-and-fix: shows exactly why photos cannot be recovered (deleted from Strava, already exist, failed)
- DEBUG logging for photo download issues to help diagnose problems
- Separate unit tests from e2e tests in tox configuration

#### 🐛 Bug Fixes

- Fix fresh photo URL fetching from API (stored URLs may expire)
- Fix placeholder URL detection for expired Strava photos

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.3.0 (2025-12-21)

#### 🚀 Features

- Add automated screenshot generation for documentation
- Add screenshots section to README.md with demo images
- Document 'No Backend Required' architecture

#### 🔧 Improvements

- Improve demo data quality for screenshots

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.2.0 (2025-12-21)

#### 🚀 Features

- Add `start_lat`/`start_lng` columns to sessions.tsv (replaces `center_lat`/`center_lng`)
- sessions.tsv now always includes GPS start coordinates for map visualization
- Add gitattributes rule to route log files to git-annex
- Add comprehensive migration tests

#### 🐛 Bug Fixes

- Fix rate limit handling in social refresh to preserve existing data

#### 📝 Documentation

- Document Strava API limitation: kudos/comments don't include athlete_id
- Simplify rebuild-sessions CLI (coordinates always included)

#### 🔄 Migration

- Run `strava-backup migrate` to rename center_lat/center_lng columns
- Or run `strava-backup rebuild-sessions` to regenerate sessions.tsv entirely

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.1.0 (2025-12-21)

#### 🚀 Features

- Initial release with Strava backup, map visualization, and FitTrackee export
- OAuth2 authentication with automatic token refresh
- Incremental activity sync with Hive-partitioned storage
- GPS tracking data stored as Parquet files
- Photo backup with automatic download
- Comments and kudos backup
- Interactive map visualization with filtering
- Statistics dashboard with charts
- GPX export functionality
- FitTrackee export support
- DataLad dataset integration
- Demo mode for testing

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))
