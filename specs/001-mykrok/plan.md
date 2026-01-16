# Implementation Plan: MyKrok - Fitness Activity Backup and Visualization

**Branch**: `001-mykrok` | **Date**: 2025-12-18 | **Spec**: [specs/001-mykrok/spec.md](spec.md)
**Input**: Feature specification from `/specs/001-mykrok/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

CLI tool to backup fitness activities (metadata, GPS tracks, photos, comments, kudos) with incremental sync, store in Hive-partitioned layout for DuckDB queries, generate interactive map visualizations with heatmap mode, and export to other platforms. Currently supports Strava as data source. MVC architecture with file-based model layer.

## Technical Context

**Language/Version**: Python 3.10+ (type hints required per constitution)
**Primary Dependencies**: stravalib (Strava API), PyArrow (Parquet), requests (FitTrackee API), DuckDB (queries)
**Storage**: File-based, Hive-partitioned directory structure (`athl={username}/ses={datetime}/`) with JSON metadata, Parquet time-series, TSV summaries
**Testing**: pytest with pytest-cov, pytest-docker for FitTrackee integration tests
**Target Platform**: Linux/macOS/Windows CLI (Python 3.10+)
**Project Type**: Single project (CLI tool with local web view for maps)
**Performance Goals**: Initial backup of 1000 activities within daily API limit; incremental backup <5 min for <50 activities; map loads <10s for 1000 routes
**Constraints**: Respect Strava rate limits (200/15min, 2000/day), FitTrackee limits (300/5min); offline browsing after sync; bounded memory (stream processing)
**Scale/Scope**: Single user, up to thousands of activities, designed for daily cron execution

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Simplicity First ✅
- **Single responsibility**: Separate modules for backup, export, visualization
- **Flat structure**: Hive partitioning is flat (`athl=X/ses=Y/`) not deeply nested
- **Explicit behavior**: No magic - CLI commands with explicit flags
- **Self-documenting**: Standard data formats (JSON, Parquet, TSV)

### Principle II: CLI-Native Design ✅
- **Text in/out**: CLI with JSON output option for machine parsing
- **Exit codes**: 0=success, non-zero for specific errors
- **Idempotent**: Incremental backup only fetches new data
- **Composable**: Can pipe output, run via cron

### Principle III: FOSS Principles ✅
- **Dependencies**: stravalib (Apache-2.0), PyArrow (Apache-2.0), requests (Apache-2.0) - all FOSS
- **No telemetry**: No data collection
- **Local config**: OAuth tokens stored locally
- **Offline capable**: All local data browsable offline after sync

### Principle IV: Efficient Resource Usage ✅
- **Incremental**: Only fetch new/changed activities
- **Rate limiting**: Built-in respect for Strava (200/15min) and FitTrackee (300/5min) limits
- **Bounded memory**: Stream GPS data processing, don't load all in memory
- **Aggressive caching**: Track sync state to avoid re-downloading

### Principle V: Test-Driven Quality ✅
- **Coverage gates**: Minimum 60% enforced in CI; target 70% for stable releases
- **CLI integration tests**: REQUIRED for all commands using real fixtures (not mocks)
- **Test-first for CLI**: CLI tests written WITH command implementation, not after
- **pytest**: Unit tests for business logic (models, services)
- **Integration tests**: FitTrackee via Docker, Strava via mocks
- **Regression tests**: Each bug fix requires a corresponding test
- **Offline tests**: Network mocked except explicit integration tests
- **No zero-coverage modules**: Every service module must have tests

### Technical Standards ✅
- Python 3.10+ with type hints
- pyproject.toml with uv
- pytest + pytest-cov
- ruff for formatting/linting
- mypy strict mode
- tox for CI orchestration

**GATE RESULT: PASS** - All constitution principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/001-mykrok/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/mykrok/
├── __init__.py
├── __main__.py          # CLI entry point
├── cli.py               # CLI commands (backup, export, view, stats)
├── config.py            # Configuration management
├── models/              # Data model layer (MVC: Model)
│   ├── __init__.py
│   ├── activity.py      # Activity entity and storage
│   ├── athlete.py       # Athlete profile and gear
│   ├── tracking.py      # GPS/sensor stream handling (Parquet)
│   └── state.py         # Sync state, export state tracking
├── services/            # Business logic layer (MVC: Controller)
│   ├── __init__.py
│   ├── strava.py        # Strava API client (wraps stravalib)
│   ├── backup.py        # Backup orchestration, incremental sync
│   ├── fittrackee.py    # FitTrackee export service
│   └── rate_limiter.py  # Rate limiting for APIs
├── views/               # Presentation layer (MVC: View)
│   ├── __init__.py
│   ├── stats.py         # Statistics calculation
│   ├── map.py           # Map/heatmap generation
│   └── browser.py       # Local activity browser
└── lib/                 # Utilities
    ├── __init__.py
    ├── gpx.py           # GPX generation/parsing
    ├── parquet.py       # Parquet utilities
    └── paths.py         # Hive-partitioned path helpers

tests/
├── conftest.py          # Shared fixtures
├── unit/
│   ├── test_models.py
│   ├── test_backup.py
│   └── test_gpx.py
├── integration/
│   ├── test_strava_api.py   # Strava API with mocks
│   └── test_fittrackee.py   # FitTrackee via Docker
└── fixtures/
    ├── activities/      # Sample activity JSON
    └── streams/         # Sample GPS/sensor data
```

### Data Directory (runtime)

```text
data/
└── athl={username}/                   # Athlete partition
    ├── sessions.tsv                   # Activity summary
    ├── gear.json                      # Equipment catalog
    ├── exports/
    │   └── fittrackee.json            # FitTrackee export state
    └── ses={datetime}/                # Session partition
        ├── info.json                  # Activity metadata
        ├── tracking.parquet           # Time-series streams
        ├── tracking.json              # Stream manifest
        └── photos/                    # Activity photos
```

**Structure Decision**: Single project structure (CLI tool). No separate frontend/backend - map visualization served via local web server from the `views/` module using static HTML/JS with Leaflet.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations identified. Design follows all constitution principles.

---

## Post-Design Constitution Verification

*Re-evaluated after Phase 1 design completion.*

### Principle I: Simplicity First ✅ VERIFIED
- Data model uses standard formats (JSON, Parquet, TSV) - no custom serialization
- CLI contract follows Unix conventions - no complex subcommand hierarchies
- Single project structure - no unnecessary microservices or packages

### Principle II: CLI-Native Design ✅ VERIFIED
- All commands support `--json` output
- Exit codes documented per command
- Environment variables for automation
- Config file for persistent settings

### Principle III: FOSS Principles ✅ VERIFIED
- All researched dependencies confirmed Apache-2.0 licensed
- stravalib, PyArrow, requests, DuckDB, Leaflet - all FOSS
- No external services required after OAuth setup

### Principle IV: Efficient Resource Usage ✅ VERIFIED
- Parquet streaming writes (PyArrow ParquetWriter) for bounded memory
- stravalib's DefaultRateLimiter handles API throttling
- Hive partitioning enables efficient DuckDB queries without full scans

### Principle V: Test-Driven Quality ✅ VERIFIED
- Coverage gates: 60% minimum, 70% target - enforced in CI
- CLI integration tests: Required for all commands with real fixtures
- Test structure defined: unit/, integration/, e2e/, fixtures/
- pytest-docker for FitTrackee integration tests
- Mocking strategy for Strava API tests
- Test tasks integrated INTO each user story phase (not as "polish")

**POST-DESIGN GATE: PASS** - All principles verified against concrete design artifacts

---

## Generated Artifacts

| Artifact | Status | Path |
|----------|--------|------|
| plan.md | ✅ Complete | specs/001-mykrok/plan.md |
| research.md | ✅ Complete | specs/001-mykrok/research.md |
| data-model.md | ✅ Complete | specs/001-mykrok/data-model.md |
| contracts/cli.md | ✅ Complete | specs/001-mykrok/contracts/cli.md |
| quickstart.md | ✅ Complete | specs/001-mykrok/quickstart.md |
| tasks.md | Pending | (Created by /speckit.tasks) |
