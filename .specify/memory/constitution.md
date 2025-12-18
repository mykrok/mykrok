<!--
Sync Impact Report
==================
Version change: 0.0.0 → 1.0.0 (initial constitution)
Modified principles: N/A (initial creation)
Added sections:
  - Core Principles (I-V)
  - Technical Standards
  - Development Workflow
  - Governance
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md: N/A (generic, compatible)
  - .specify/templates/spec-template.md: N/A (generic, compatible)
  - .specify/templates/tasks-template.md: N/A (generic, compatible)
Follow-up TODOs: None
-->

# Strava Backup Constitution

## Core Principles

### I. Simplicity First

All features MUST solve a real problem with the minimum viable implementation. No speculative features, no premature abstractions, no over-engineering.

**Rules:**
- Single responsibility: each module does one thing well
- Flat is better than nested: avoid deep directory hierarchies
- Explicit is better than implicit: no magic behavior
- If a feature requires extensive documentation to explain, simplify the feature

**Rationale:** A backup tool must be reliable and maintainable. Complexity breeds bugs and abandonment.

### II. CLI-Native Design

The tool MUST be fully functional from the command line with no GUI dependency. All operations are scriptable and composable.

**Rules:**
- Text in, text out: stdin/arguments as input, stdout for data, stderr for errors
- Exit codes MUST be meaningful (0=success, non-zero=specific error types)
- Support both human-readable and machine-parseable (JSON) output formats
- Operations MUST be idempotent where possible

**Rationale:** CLI tools integrate with cron, scripts, and automation pipelines essential for reliable backups.

### III. FOSS Principles

The project MUST remain Free and Open Source Software, respecting user freedoms and privacy.

**Rules:**
- All dependencies MUST have FOSS-compatible licenses
- No telemetry or data collection without explicit user opt-in
- Configuration stored locally, never in external services
- Users MUST be able to run the tool fully offline after authentication

**Rationale:** Backup tools handle sensitive personal data; users must have full control and auditability.

### IV. Efficient Resource Usage

The tool MUST minimize resource consumption: network requests, disk I/O, memory, and CPU.

**Rules:**
- Incremental operations: only fetch/process what changed
- Rate limiting MUST respect API constraints
- Memory usage MUST be bounded regardless of data size (stream, don't load all)
- Cache aggressively but invalidate correctly

**Rationale:** Backups often run unattended on low-power devices or metered connections.

### V. Test-Driven Quality

All non-trivial functionality MUST have automated tests. Tests document expected behavior.

**Rules:**
- New features require tests before merge
- Bug fixes require regression tests
- Integration tests for API interactions (use mocks/fixtures)
- Tests MUST run without network access (except explicitly marked integration tests)

**Rationale:** A backup tool that fails silently or corrupts data is worse than no backup at all.

## Technical Standards

**Language**: Python 3.10+ (type hints required)
**Package Management**: pyproject.toml with uv/pip
**Testing**: pytest with pytest-cov
**Linting**: ruff for formatting and linting
**Type Checking**: mypy with strict mode
**CI**: tox for local and CI test orchestration

**Code Style:**
- Maximum line length: 88 characters (ruff default)
- Type annotations on all public functions
- Docstrings for public APIs only (code should be self-documenting)
- No global mutable state

## Development Workflow

**Branch Strategy:**
- `master` branch is always releasable
- Feature branches for new development
- All changes via pull request with passing CI

**Commit Standards:**
- Conventional commits format: `type: description`
- Types: feat, fix, docs, test, refactor, chore
- Each commit should be atomic and bisectable

**Release Process:**
- Semantic versioning (MAJOR.MINOR.PATCH)
- CHANGELOG.md updated with each release
- Tagged releases only

## Governance

This constitution defines the non-negotiable principles for the strava-backup project. All contributions MUST align with these principles.

**Amendment Process:**
1. Propose change via issue or PR
2. Document rationale and impact
3. Update version per semantic rules below
4. Update dependent documentation

**Version Policy:**
- MAJOR: Principle removal or fundamental redefinition
- MINOR: New principle or significant expansion
- PATCH: Clarifications and wording improvements

**Compliance:**
- PRs MUST pass constitution check in plan phase
- Complexity violations require explicit justification
- Reviewers verify principle alignment

**Version**: 1.0.0 | **Ratified**: 2025-12-18 | **Last Amended**: 2025-12-18
