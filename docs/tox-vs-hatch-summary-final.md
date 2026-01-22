# Tox vs Hatch: Practical Comparison Summary

Based on actual migration of mykrok project from tox to hatch.

## Feature Comparison

| Aspect | tox + tox-uv | hatch |
|--------|--------------|-------|
| **Single command for all** | `tox` | `make` (wrapper needed) |
| **Unified summary at end** | ✅ shows pass/fail per env | ❌ sequential output only |
| **Config location** | `tox.ini` (separate file) | `pyproject.toml` (single file) |
| **Python version matrix** | ✅ `py3{10,11,12,13}` | ✅ `[[matrix]]` |
| **Auto Python download** | ✅ (via uv) | ✅ (via uv) |
| **Lint/type/JS environments** | ✅ native | ✅ native |
| **Coverage support** | ✅ | ✅ |
| **CI plugin required** | `tox-gh-actions` | none |
| **Parallel matrix execution** | ✅ `tox -p auto` | ❌ (single env at a time)* |
| **Interactive shell** | ❌ | ✅ `hatch shell <env>` |
| **Environment location** | `.tox/` (project-local) | `~/.local/share/hatch/` (central)** |

\* `hatch test --all` runs matrix sequentially; parallelism within tests via pytest-xdist
\** Can be configured to be project-local

## Command Equivalents

| Task | tox | hatch |
|------|-----|-------|
| Run everything | `tox` | `make` or chain commands |
| Specific Python | `tox -e py312` | `hatch test -py 3.12` |
| With coverage | `tox -e cov` | `hatch test --cover` |
| Lint only | `tox -e lint` | `hatch run lint:check` |
| Type check only | `tox -e type` | `hatch run types:check` |
| JS tests | `tox -e jslint,jstest` | `hatch run js:all` |
| Parallel envs | `tox -p auto` | not available |
| Recreate envs | `tox -r` | `hatch env prune` |

## Pros and Cons

### Tox Advantages
- **Unified summary**: Clear pass/fail status for each environment at end
- **Parallel execution**: `tox -p auto` runs environments concurrently
- **Battle-tested**: 15+ years, very stable
- **Purpose-built**: Designed specifically for test orchestration

### Hatch Advantages
- **Single config file**: Everything in pyproject.toml
- **No CI plugin**: GitHub Actions matrix handles version selection
- **Interactive shells**: `hatch shell <env>` for debugging
- **Modern tooling**: Native uv integration, TOML config

### Tox Disadvantages
- Separate config file (tox.ini)
- Needs tox-gh-actions plugin for CI
- INI format less expressive than TOML

### Hatch Disadvantages
- No unified summary across environments
- No parallel environment execution
- Requires Makefile or script for "run everything" workflow
- Newer, less mature for test orchestration

## Verdict

- **Choose tox** if: unified summary and parallel execution matter, or you have complex multi-environment needs
- **Choose hatch** if: single config file is priority, you want interactive shells, or your CI handles the matrix

Both tools work well. The choice depends on workflow preferences.
