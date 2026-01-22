# Changelog

## v1.4.1 (2026-01-21)

#### 🐛 Bug Fixes

- Fix duplicate files in wheel package preventing PyPI upload
  - Remove redundant force-include directive in pyproject.toml

#### 🔧 Improvements

- Add PyPI upload instructions to release checklist
  - Document build and upload process using twine
  - Include PyPI credential configuration options
  - Add package verification steps

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v1.4.0 (2025-12-31)

#### 🚀 Features

- Add photo markers to session view charts and maps
  - Camera icons on elevation and activity charts at positions where photos were taken
  - Photo markers on session map along the track path
  - Hover shows photo preview popup with thumbnail, navigation, and session info
  - Click opens full PhotoViewer modal
- Display activity description on session detail pages
  - Shows Strava description with clickable links
  - Styled with accent border matching app theme
- Add automatic social refresh during sync
  - Default syncs now update kudos/comments for activities from past 7 days
  - Configurable via `--refresh-social-days` option
- Auto-generate `athletes.tsv` during sync if missing
  - Fixes `create-browser` failing after first sync

#### 🔧 Improvements

- Add reusable PhotoPopup component for consistent photo popups across map, session, and chart views
- Add migration for old CLI commands in Makefile (`mykrok view map` → `mykrok create-browser`)
- Move inline imports to module level per code style guidelines

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v1.3.0 (2025-12-29)

#### 🚀 Features

- Add timezone history tracking for correct local times
  - Detect timezone from GPS coordinates using `timezonefinder` (optional dependency)
  - Per-athlete timezone history survives Strava re-syncs
  - Sanity checks: reject rapid changes (<4h), validate timezone names, warn about flickering
  - Add `rebuild-timezones` CLI command to build history from existing activities
  - Auto-detect timezone during sync for new GPS-enabled activities
- Add Stats view with activity heatmaps
  - Activity Calendar: GitHub-style year heatmap with week totals and date filtering
  - Activity Timing: hour-of-day × day-of-week heatmap showing workout patterns
  - Unified rendering with consistent color scales and tooltips
- Add `[full]` optional dependency for typical user deployments (`pip install mykrok[full]`)

#### 🐛 Bug Fixes

- Fix `datetime_local` not passed to StatsView sessions (Activity Timing showed wrong hours)
- Fix footer row height to match regular rows in heatmaps

#### 🔧 Improvements

- Add Total row to Activity Timing heatmap
- Fix colorbar max value calculation in heatmaps

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v1.2.0 (2025-12-27)

#### 📚 Documentation

- Add MkDocs documentation site with Diataxis organization (Tutorials, How-to, Reference, Explanation)
- Add Read the Docs integration and badge
- Add screenshots to documentation (reused from README)
- Add Apache hosting guide with git-annex symlink configuration
- Add MyKrok logo to documentation site

#### 🔧 Improvements

- Deploy documentation alongside demo on GitHub Pages (`/docs/` subdirectory)

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v1.1.0 (2025-12-27)

#### 🚀 Features

- Add viewport filter to filter activities list to current map view (toggle button with focus icon)
- Add `--lean-update` option to sync command (skip syncs when local data is current)

#### 🐛 Bug Fixes

- Fix track not loading when navigating directly to URL with track parameter
- Fix `marker.addTo is not a function` error in map-browser

#### 🔧 Improvements

- Extend `--lean-update` to also remove log file when no changes
- Add debug logging for track loading
- Fix View on Map button behavior

#### 🔄 CI

- Fix git-annex installation in GitHub Actions

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v1.0.0 (2025-12-26)

#### 🎉 Project Rename

- Rename project from "strava-backup" to "MyKrok" (Ukrainian "мій крок" = "my step")
- CLI command changed from `strava-backup` to `mykrok`
- Config directory changed from `.strava-backup/` to `.mykrok/`
- Package name changed from `strava-backup` to `mykrok`
- GitHub organization: https://github.com/mykrok/mykrok

#### 🚀 Features

- Add `-o/--output` option to `create-browser` command for custom output filename (default: mykrok.html)

#### 🔧 Improvements

- Generalize descriptions to be platform-agnostic ("fitness activity backup" instead of "Strava backup")
- Consolidate and fix application icon

#### 🔄 Migration

- Fix migration to properly find and update config directory
- Add migration for dataset template files (README, Makefile, .gitignore)
- Update all legacy `strava-backup` references in template files

Legacy configuration paths are still supported for backward compatibility:
- `.strava-backup/config.toml` → `.mykrok/config.toml`
- `.strava-backup.toml` → `.mykrok/config.toml`
- `STRAVA_BACKUP_CONFIG` env var → `MYKROK_CONFIG`
- `STRAVA_BACKUP_DATA_DIR` env var → `MYKROK_DATA_DIR`

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.9.1 (2025-12-23)

#### 🐛 Bug Fixes

- Fix missing photo-viewer-utils.js asset (caused JavaScript error on page load)

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.9.0 (2025-12-22)

#### 🚀 Features

- Add PhotoViewer component with keyboard navigation (←/→/Escape)
- Add permalink support for sharing map views, tracks, and photos
- Add photo navigation in map popups (prev/next buttons)
- Add multi-athlete authentication plan (features/multi-athlete/plan.md)

#### 🐛 Bug Fixes

- Fix session view photos to load from info.json (works on servers without directory listing)
- Fix URL state handling and date filtering consistency
- Fix popup/track URL parameters clearing on new selection

#### 🔧 Improvements

- Add validation to create-browser: require athletes.tsv
- Add unit tests for backup logic (related sessions, photo recovery)
- Update CLI contract and quickstart.md to match implementation
- Add favicon.svg to prevent 404 errors

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.8.0 (2025-12-22)

#### 🚀 Features

- Add photo indicators to sessions and activities lists

#### 🐛 Bug Fixes

- Fix map tracks not respecting date/type/search filters

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.7.1 (2025-12-22)

#### 🐛 Bug Fixes

- Fix photo display for git-annex symlinks (strip @ suffix from directory listing)
- Fix photo path regex: use `\+` not `\\+` to match timezone in created_at

#### 🔧 Improvements

- Fix gh-pages workflow: fetch remote branch if local doesn't exist
- Fix CI workflow: add Node.js setup for JavaScript linting/testing

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.7.0 (2025-12-22)

#### 🚀 Features

- Bold selected track on map for better visibility
- Color-coded activity type labels in UI

#### 🔧 Improvements

- Extract JavaScript to external modules with ESLint linting and Jest tests
- Add REUSE 3.3 compliant licensing (REUSE.toml, LICENSES/)

#### 📝 License

- Change license from MIT to Apache-2.0

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

## v0.6.0 (2025-12-22)

#### 🚀 Features

- Add date range expand buttons (week/month/year) in filter bar
- Add clickable dates in activity popups to filter by that date
- Add version display to map header

#### 🔧 Improvements

- Preserve filter state when navigating to "View all sessions"
- Improve date filter sync and marker focus behavior
- Simplify CLI by removing deprecated commands

#### 🐛 Bug Fixes

- Fix Activities panel resize and marker focus issues

#### Authors: 1

- Yaroslav Halchenko ([@yarikoptic](https://github.com/yarikoptic))

---

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

- Initial release with activity backup (Strava), map visualization, and FitTrackee export
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
