# Tox vs Hatch: Comprehensive Comparison

## 1. Matrix Environment Specification

### Tox Configuration (INI-based)

```ini
# tox.ini
[tox]
envlist = py3{10,11,12,13},lint,type
isolated_build = true
skip_missing_interpreters = true

[testenv]
deps = .[test]
commands = pytest tests/ {posargs}

[testenv:lint]
skip_install = true
deps = .[devel]
commands = ruff check src/ tests/

[testenv:type]
skip_install = true
deps = .[devel]
commands = mypy --ignore-missing-imports src/
```

**Key characteristics:**
- Uses brace expansion syntax `py3{10,11,12,13}` for version matrices
- Each environment is a distinct entry in `envlist`
- Environment variants use `[testenv:NAME]` sections
- Must have Python versions available on PATH (or skip with `skip_missing_interpreters`)

### Hatch Configuration (TOML-based in pyproject.toml)

```toml
# pyproject.toml
[tool.hatch.envs.test]
dependencies = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
]

[tool.hatch.envs.test.scripts]
run = "pytest tests/ {args}"
cov = "pytest --cov-report=term-missing --cov=src {args}"

[[tool.hatch.envs.test.matrix]]
python = ["3.10", "3.11", "3.12", "3.13"]

[tool.hatch.envs.lint]
detached = true  # Don't install the project
dependencies = [
    "ruff>=0.1.0",
]

[tool.hatch.envs.lint.scripts]
check = "ruff check src/ tests/"
format = "ruff format src/ tests/"

[tool.hatch.envs.types]
detached = true
dependencies = [
    "mypy>=1.0",
]

[tool.hatch.envs.types.scripts]
check = "mypy --ignore-missing-imports src/"
```

**Key characteristics:**
- Uses TOML array tables `[[tool.hatch.envs.test.matrix]]` for matrices
- Produces Cartesian product of matrix variables
- Generated env names: `test.py3.10`, `test.py3.11`, etc.
- Can auto-download Python distributions via uv if missing (Hatch 1.8+)

### Multi-dimensional Matrix Example (Hatch)

```toml
[[tool.hatch.envs.test.matrix]]
python = ["3.10", "3.11", "3.12"]
django = ["4.2", "5.0"]
```

This creates 6 environments: `test.py3.10-4.2`, `test.py3.10-5.0`, `test.py3.11-4.2`, etc.

In tox, equivalent would be:
```ini
[tox]
envlist = py3{10,11,12}-django{42,50}

[testenv]
deps =
    django42: Django>=4.2,<4.3
    django50: Django>=5.0,<5.1
```

---

## 2. Local Execution

### Tox Local Commands

```bash
# Run all environments
tox

# Run specific Python versions
tox -e py310,py311

# Run lint + type checking
tox -e lint,type

# Run with pytest arguments
tox -e py312 -- -v -k "test_specific"

# Parallel execution
tox -p auto
```

### Hatch Local Commands

```bash
# Run in default environment
hatch run test:run

# Run across ALL matrix environments
hatch run test:run --all
# Or: hatch test --all

# Run for specific Python version
hatch run +py=3.12 test:run
# Or: hatch test -py 3.12

# Run lint (non-matrix environment)
hatch run lint:check

# Run type checking
hatch run types:check

# With pytest arguments
hatch run test:run -- -v -k "test_specific"

# Show all environments
hatch env show --ascii
```

### Key Differences for Local Execution

| Aspect | Tox | Hatch |
|--------|-----|-------|
| **Syntax** | `tox -e py310,py311` | `hatch run +py=3.10,3.11 test:run` |
| **All versions** | `tox` (runs envlist) | `hatch test --all` |
| **Missing Python** | Error (unless `skip_missing_interpreters`) | Auto-downloads via uv |
| **Interactive shell** | Not supported | `hatch shell test.py3.12` |
| **Parallel** | `tox -p auto` | `hatch test --parallel` (within env) |

**Gotcha for Hatch:** Without `--all`, Hatch only runs the first compatible environment. This differs from tox which runs the full envlist by default.

---

## 3. GitHub Actions Integration

### Tox with tox-gh-actions

```ini
# tox.ini
[gh-actions]
python =
    3.10: cov
    3.11: cov
    3.12: cov
    3.13: cov
```

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install CI dependencies
        run: uv pip install --system -e ".[ci]"
      - name: Run tox
        run: tox  # tox-gh-actions auto-selects envs based on Python version
```

**How tox-gh-actions works:**
1. GH Actions matrix sets up Python 3.12
2. tox-gh-actions reads `[gh-actions]` section
3. Maps Python 3.12 to environments: `cov`
4. Runs only those environments

### Hatch with GitHub Actions (Recommended Approach)

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install Hatch
        run: pipx install hatch
      - name: Run tests with coverage
        run: hatch test --cover
      - name: Upload coverage
        uses: codecov/codecov-action@v4

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Hatch
        run: pipx install hatch
      - name: Run linting
        run: hatch run lint:check
      - name: Run type checking
        run: hatch run types:check
```

**Key difference:** Hatch maintainers recommend letting GitHub Actions manage the Python matrix, not Hatch.

### Comparison Table

| Aspect | tox-gh-actions | Hatch + GH Actions |
|--------|----------------|-------------------|
| **Extra plugin** | Yes (`tox-gh-actions`) | No |
| **Config location** | `[gh-actions]` in tox.ini | GH Actions workflow only |
| **Matrix defined in** | Both tox.ini AND workflow | Workflow only |
| **Version mapping** | Explicit `3.10: py310,lint` | Implicit (uses PATH python) |
| **Duplication** | Yes (versions in 2 places) | No |

---

## 4. Generic CI / `act` Compatibility

### Tox with `act`

Tox works well with `act` because:
- `tox` command is self-contained
- No GitHub-specific magic (tox-gh-actions reads `GITHUB_ACTIONS` env var)
- When `GITHUB_ACTIONS` is not set, tox runs full envlist

```bash
# Running locally with act
act -j test

# Or just run tox directly (recommended)
tox -e py312,lint,type
```

### Hatch with `act`

```bash
# act runs the workflow
act -j test

# But for local testing, just use hatch directly
hatch test -py 3.12
hatch run lint:check
```

**Advantage:** Hatch's approach of delegating matrix to GH Actions means no special CI plugin needed.

### Generic CI (GitLab, Jenkins, etc.)

**Tox:** Works great with any CI. Just `pip install tox && tox`.

```yaml
# .gitlab-ci.yml example
test:
  image: python:3.12
  script:
    - pip install tox
    - tox -e py312,lint,type
```

**Hatch:** Similarly portable.

```yaml
# .gitlab-ci.yml example
test:
  image: python:3.12
  script:
    - pipx install hatch
    - hatch test
    - hatch run lint:check
```

---

## 5. Environment Creation & Management

### Tox Environment Model

```
.tox/
├── py310/          # Full virtualenv
├── py311/          # Full virtualenv
├── py312/          # Full virtualenv
├── lint/           # Separate virtualenv
└── type/           # Separate virtualenv
```

- Each environment is completely isolated
- Dependencies reinstalled per environment
- Environments recreated on config change or `tox -r`

### Hatch Environment Model

```
~/.local/share/hatch/env/virtual/  # Default location (configurable)
├── mykrok/
│   ├── test.py3.10/
│   ├── test.py3.11/
│   ├── lint/
│   └── types/
```

- Environments stored centrally (not in project by default)
- Interactive shell access: `hatch shell lint`
- Environments auto-created on first use

**Configuration for project-local environments:**
```toml
[tool.hatch.envs.default]
path = ".hatch"
```

---

## 6. Pros/Cons for Migration

### Reasons to Stay with Tox

1. **Mature & Battle-tested**: 15+ years of development
2. **Your config already works**: No migration effort needed
3. **Better npm/external tool support**: `allowlist_externals` and `commands_pre` work well
4. **tox-uv integration**: Already provides speed benefits
5. **No learning curve**: Team already knows tox
6. **Parallel execution**: `tox -p auto` runs environments concurrently

### Reasons to Consider Hatch

1. **Single config file**: Everything in pyproject.toml (no tox.ini)
2. **Auto Python downloads**: Missing Python versions fetched via uv
3. **Interactive shells**: `hatch shell test.py3.12` for debugging
4. **No CI plugin needed**: Simpler GH Actions integration
5. **Modern TOML config**: Better editor support, syntax highlighting
6. **Named scripts**: `hatch run test:cov` is more readable than `tox -e cov`

### Gotchas If Migrating

1. **Default behavior differs**: Hatch runs single env by default; tox runs full envlist
2. **JavaScript tasks**: No native support; would need workarounds
3. **Environment location**: Central by default, not project-local
4. **`skip_install` equivalent**: Use `detached = true` in Hatch
5. **`commands_pre` equivalent**: Not directly supported; use scripts

---

## 7. npm/JavaScript Support in Hatch

Hatch doesn't have native npm support, but it's workable with shell scripts:

### Basic Setup

```toml
[tool.hatch.envs.js]
detached = true      # Don't install the Python project
skip-install = true  # Skip Python package installation entirely

[tool.hatch.envs.js.scripts]
# Chain install with each command (no commands_pre equivalent)
lint = "npm install --silent && npm run lint"
test = "npm install --silent && npm test"
# Or use script chaining
_install = "npm install --silent"
lint-only = "npm run lint"
test-only = "npm test"
all = ["_install", "lint-only", "test-only"]
```

### Usage

```bash
hatch run js:lint
hatch run js:test
hatch run js:all  # Install once, run both
```

### Obstacles & Workarounds

| Issue | Tox Solution | Hatch Workaround |
|-------|--------------|------------------|
| Pre-command setup | `commands_pre = npm install` | Chain in script: `npm install && npm run lint` |
| External commands | `allowlist_externals = npm` | Not needed (less safe, just works) |
| Separate install step | Built-in | Use script chaining with `_install` prefix |
| node_modules caching | Not handled | Not handled (same situation) |
| CI single command | `tox -e jslint,jstest` | `hatch run js:all` or multiple commands |

### Comparison: Equivalent Configs

**Tox:**
```ini
[testenv:jslint]
skip_install = true
allowlist_externals = npm
commands_pre = npm install --silent
commands = npm run lint

[testenv:jstest]
skip_install = true
allowlist_externals = npm
commands_pre = npm install --silent
commands = npm test
```

**Hatch:**
```toml
[tool.hatch.envs.js]
detached = true
skip-install = true

[tool.hatch.envs.js.scripts]
lint = "npm install --silent && npm run lint"
test = "npm install --silent && npm test"
```

### Verdict

**Hatch JS support is adequate but less elegant:**
- Works fine for simple npm commands
- Missing `commands_pre` means repetition or script chaining
- No explicit external command allowlisting (security consideration)
- Functionally equivalent for most use cases

**Migration effort: Low** - Just rewrite the commands as shell strings.

---

## 8. Recommendation

**For projects with JavaScript integration or complex environments, stay with tox:**

1. **JavaScript integration**: `jslint` and `jstest` environments using npm work cleanly in tox
2. **Complex environments**: `e2e` environments with `passenv`, `commands_pre` (playwright install) are harder in Hatch
3. **tox-uv already provides speed**: Fast environment creation already achieved

**Consider Hatch for new, simpler projects** that:
- Are Python-only (no npm/JS)
- Don't need complex environment setup
- Want single-file configuration

**Hybrid approach:** Use `hatch build` for building (with hatchling backend) while keeping `tox` for test orchestration.
