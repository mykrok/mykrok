# Testing Strategy Specification

**Created**: 2026-01-15
**Status**: Active
**Current Coverage**: 43% Python, 40% overall (including JS)
**Target Coverage**: 70%+

## Related Documents

- **spec.md**: Testing Requirements section defines coverage targets and test types
- **plan.md**: Principle V defines test-driven quality standards
- **tasks.md**: Test tasks integrated INTO each user story phase
- **contracts/cli.md**: Testing contracts for each CLI command
- **checklists/release.md**: Coverage gates for releases

## Overview

This document specifies the testing strategy for MyKrok, prioritizing real data
integration tests over mocked unit tests to maximize value and catch real
regressions.

## Testing Philosophy

1. **Real data over mocks**: Prefer tests that operate on actual fixture data
   representing real-world scenarios
2. **CLI-first testing**: CLI tests exercise the entire stack (CLI → services →
   models → file I/O), providing high coverage with fewer tests
3. **Fixture reuse**: Leverage the existing `generate_fixtures.py` to create
   consistent, realistic test data
4. **Incremental improvement**: Focus on high-impact areas first
5. **Tests WITH implementation**: Tests are written alongside code, not after

## Current State Analysis

### Coverage by Module (as of 2026-01-15)

| Module | Coverage | Statements | Notes |
|--------|----------|------------|-------|
| `cli.py` | 0% | 730 | **Highest priority** - main entry point |
| `fittrackee.py` | 0% | 117 | FitTrackee export service |
| `stats.py` | 0% | 110 | Stats view generation |
| `gpx.py` | 14% | 134 | GPX processing |
| `logging.py` | 32% | 73 | Logging utilities |
| `backup.py` | 38% | 664 | Core backup service (largest) |
| `strava.py` | 43% | 187 | Strava API client |
| `tracking.py` | 51% | 119 | Activity tracking |
| `parquet.py` | 55% | 105 | Data serialization |
| `config.py` | 59% | 182 | Configuration handling |
| `map.py` | 63% | 59 | Map view generation |
| `paths.py` | 69% | 89 | Path utilities |
| `gh_pages.py` | 69% | 133 | GitHub Pages generation |
| `activity.py` | 71% | 194 | Activity model |
| `athlete.py` | 70% | 102 | Athlete model |
| `datalad.py` | 76% | 56 | DataLad integration |
| `migrate.py` | 78% | 255 | Migration utilities |
| `state.py` | 82% | 223 | State management |
| `timezone.py` | 87% | 176 | Timezone handling |
| `rate_limiter.py` | 95% | 92 | Rate limiting |

### Test Types

- **Unit tests**: `tests/unit/` - Isolated component tests
- **Integration tests**: `tests/integration/` - API client tests with mocks
- **E2E tests**: `tests/e2e/` - Browser-based tests (Playwright)
- **JS tests**: `tests/js/` - JavaScript utility tests

## Implementation Phases

### Phase 0: Document Testing Strategy (This Document)

- [x] Analyze current coverage
- [x] Document testing philosophy
- [x] Define implementation phases
- [x] Specify CLI test requirements
- [x] Integrate testing into spec documents (spec.md, plan.md, tasks.md)
- [x] Add testing contracts to contracts/cli.md
- [x] Add coverage gates to checklists/release.md

### Phase 1: CLI Integration Tests (Highest Priority)

**Goal**: Test CLI commands against real fixture data

**Approach**:
- Use Click's `CliRunner` for invoking commands
- Generate fixtures using `tests/e2e/fixtures/generate_fixtures.py`
- Verify command output and file system changes

**Testing Contracts**: See `contracts/cli.md` for detailed test specifications
for each command including example test code.

**Commands to Test**:

#### 1.1 `rebuild-sessions`
```
mykrok rebuild-sessions
```
- **Input**: Data directory with activity files
- **Expected**: Regenerated `sessions.tsv` matching activity data
- **Verification**:
  - Command exits successfully
  - `sessions.tsv` exists and has correct columns
  - Row count matches activity count
  - Data integrity (dates, distances, etc.)

#### 1.2 `rebuild-timezones`
```
mykrok rebuild-timezones
```
- **Input**: Data directory with GPS tracks
- **Expected**: `timezones.tsv` with detected timezones
- **Verification**:
  - Timezone entries for activities with GPS data
  - Correct timezone names (e.g., "America/New_York")

#### 1.3 `migrate`
```
mykrok migrate [--dry-run]
```
- **Input**: Data directory with legacy structure
- **Expected**: Updated file structure and paths
- **Verification**:
  - Dry run reports changes without modifying files
  - Actual run applies migrations
  - Idempotent (running twice produces same result)

#### 1.4 `gpx`
```
mykrok gpx <session_dir>
```
- **Input**: Session directory with stream data
- **Expected**: Generated GPX file
- **Verification**:
  - Valid GPX XML structure
  - Correct waypoint count
  - Coordinates within expected bounds

#### 1.5 `create-browser`
```
mykrok create-browser -o <output_dir>
```
- **Input**: Data directory with activities
- **Expected**: Static browser files
- **Verification**:
  - `index.html` exists
  - JavaScript assets copied
  - `sessions.tsv` embedded or linked

#### 1.6 `view stats`
```
mykrok view stats
```
- **Input**: Data directory with activities
- **Expected**: Statistics output
- **Verification**:
  - Correct totals (distance, time, count)
  - Breakdown by activity type
  - Date range filtering works

#### 1.7 `gh-pages`
```
mykrok gh-pages
```
- **Input**: Git repository with data
- **Expected**: gh-pages branch with browser files
- **Verification**:
  - Branch created/updated
  - Contains required files
  - Worktree cleaned up

### Phase 2: Service Tests with Mocked APIs

**Goal**: Test service layer with controlled inputs

#### 2.1 `backup.py` (38% → 70%)
- Sync workflow with various activity types
- Error handling (rate limits, network failures)
- Photo download and deduplication
- Incremental sync logic
- Social data refresh

#### 2.2 `fittrackee.py` (0% → 60%)
- Authentication flow
- Activity upload
- Sport type mapping
- Error handling

#### 2.3 `gpx.py` (14% → 70%)
- GPX parsing
- Track simplification
- Coordinate handling
- Edge cases (empty tracks, single point)

### Phase 3: Quick Wins (Unit Tests)

**Goal**: Increase coverage of well-structured modules

#### 3.1 `strava.py` (43% → 70%)
- Token refresh logic
- Rate limit handling
- API error responses

#### 3.2 `config.py` (59% → 80%)
- Missing config file
- Malformed TOML
- Environment variable overrides
- Token persistence

#### 3.3 `parquet.py` (55% → 75%)
- TSV generation edge cases
- Column type handling
- Large file handling

#### 3.4 `tracking.py` (51% → 75%)
- Tracking file operations
- State transitions
- Error recovery

## Test Fixtures

### Primary Fixture Generator

Located at: `tests/e2e/fixtures/generate_fixtures.py`

Creates:
- Two athletes (alice, bob)
- 10+ sessions per athlete
- Multiple activity types (Run, Ride, Swim, Hike)
- GPS tracks with sensor data (HR, cadence, power)
- Photos, kudos, comments
- A shared run (same datetime for both athletes)

### CLI Test Fixture Setup

```python
@pytest.fixture
def cli_data_dir(tmp_path: Path) -> Path:
    """Generate realistic data for CLI tests."""
    from tests.e2e.fixtures.generate_fixtures import generate_all

    data_dir = tmp_path / "data"
    generate_all(data_dir, seed=42)  # Deterministic
    return data_dir

@pytest.fixture
def cli_runner() -> CliRunner:
    """Click CLI test runner."""
    return CliRunner()
```

## Success Criteria

| Phase | Target Coverage | Key Metrics |
|-------|-----------------|-------------|
| Phase 1 | 55% | All CLI commands tested |
| Phase 2 | 65% | Service layer covered |
| Phase 3 | 70% | Unit test gaps filled |

## Maintenance

- Run `tox -e cov` to generate coverage reports
- Update this document when adding new modules
- Review coverage quarterly
