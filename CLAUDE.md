# strava-backup Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-18

## Active Technologies

- Python 3.10+ (type hints required per constitution) + stravalib (Strava API), PyArrow (Parquet), requests (FitTrackee API), DuckDB (queries) (001-strava-backup)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.10+ (type hints required per constitution): Follow standard conventions

## Recent Changes

- 001-strava-backup: Added Python 3.10+ (type hints required per constitution) + stravalib (Strava API), PyArrow (Parquet), requests (FitTrackee API), DuckDB (queries)

<!-- MANUAL ADDITIONS START -->

## Pre-commit Checks

**IMPORTANT**: Before every commit, run lint and type checks:

```bash
uv run tox -e lint,type
```

Both must pass before committing. Fix any issues before proceeding.

## Release Process

**IMPORTANT**: Before creating any release, follow the checklist at:
`specs/001-strava-backup/checklists/release.md`

Minimum verification before release:

```bash
# Run ALL tests (Python + JavaScript)
uv run tox
npm test

# Verify JavaScript assets exist
ls src/strava_backup/assets/map-browser/*.js
```

All tests must pass before tagging a release. The v0.9.0 → v0.9.1 incident
(missing photo-viewer-utils.js) could have been caught by running tests first.

<!-- MANUAL ADDITIONS END -->
