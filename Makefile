# Makefile for mykrok development tasks
# Uses hatch for Python environment management

.PHONY: all test test-all lint type js clean help

# Default: full test suite (equivalent to old `tox` command)
# Runs: lint + type + all Python versions with coverage + JS tests
all: lint type test-cov js

# Run Python tests (current Python version only)
test:
	hatch test

# Run ALL tests: Python (all versions) + JavaScript
test-all:
	hatch test --all
	hatch run js:all

# Run Python tests (all versions) with coverage
test-cov:
	hatch test --all --cover

# Lint Python code
lint:
	hatch run lint:check

# Fix lint issues automatically
lint-fix:
	hatch run lint:fix

# Format code
format:
	hatch run lint:format

# Type checking
type:
	hatch run types:check

# JavaScript lint and tests
js:
	hatch run js:all

js-lint:
	hatch run js:lint

js-test:
	hatch run js:test

# Integration tests
integration:
	hatch run integration:run

# E2E tests (requires playwright)
e2e:
	hatch run e2e:run

# Documentation
docs:
	hatch run docs:build

docs-serve:
	hatch run docs:serve

# CI: same as all (full test suite)
ci: all

# Clean hatch environments
clean:
	hatch env prune

help:
	@echo "Available targets:"
	@echo "  all        - Run all tests (Python + JavaScript) [default]"
	@echo "  test       - Run Python tests (current version)"
	@echo "  test-all   - Run Python tests (all versions) + JS tests"
	@echo "  test-cov   - Run tests with coverage"
	@echo "  lint       - Run linter"
	@echo "  lint-fix   - Auto-fix lint issues"
	@echo "  format     - Format code"
	@echo "  type       - Run type checking"
	@echo "  js         - Run JavaScript lint + tests"
	@echo "  integration- Run integration tests"
	@echo "  e2e        - Run E2E tests (requires playwright)"
	@echo "  docs       - Build documentation"
	@echo "  docs-serve - Serve docs with live reload"
	@echo "  ci         - Run lint + type + all tests"
	@echo "  clean      - Remove hatch environments"
