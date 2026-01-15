# MyKrok Development Guidelines

> **Note**: This project was formerly known as "strava-backup".

Auto-generated from all feature plans. Last updated: 2025-12-23

## Active Technologies

- Python 3.10+ (type hints required per constitution) + stravalib (Strava API), PyArrow (Parquet), requests (FitTrackee API), DuckDB (queries) (001-mykrok)

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

- 001-mykrok: Added Python 3.10+ (type hints required per constitution) + stravalib (Strava API), PyArrow (Parquet), requests (FitTrackee API), DuckDB (queries)

<!-- MANUAL ADDITIONS START -->

## Git Workflow

**CRITICAL**: NEVER checkout or modify any branch other than the one you are
currently working on unless explicitly requested by the user. Stay on the
current branch for all operations.

## Pre-commit Checks

**IMPORTANT**: Before every commit, run lint and type checks:

```bash
uv run tox -e lint,type
```

Both must pass before committing. Fix any issues before proceeding.

## Release Process

**IMPORTANT**: Before creating any release, follow the checklist at:
`specs/001-mykrok/checklists/release.md`

Minimum verification before release:

```bash
# Run ALL tests (Python + JavaScript)
uv run tox
npm test

# Verify JavaScript assets exist
ls src/mykrok/assets/map-browser/*.js
```

All tests must pass before tagging a release. The v0.9.0 → v0.9.1 incident
(missing photo-viewer-utils.js) could have been caught by running tests first.

<!-- MANUAL ADDITIONS END -->
