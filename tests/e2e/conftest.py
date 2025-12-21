"""Pytest configuration for e2e tests.

Configures playwright for headless browser testing.

Prerequisites:
    1. Install playwright: pip install pytest-playwright
    2. Install browser deps: sudo playwright install-deps chromium
    3. Install browser: playwright install chromium

If system deps are missing, tests will be skipped.
"""

from __future__ import annotations

import sys

import pytest


def _check_browser_available() -> bool:
    """Check if Playwright browser is available and working."""
    try:
        # Try to import playwright and check if chromium works
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            browser.close()
        return True
    except Exception:
        return False


# Check browser availability once at module load
_BROWSER_AVAILABLE = None


def pytest_configure(config: pytest.Config) -> None:  # noqa: ARG001
    """Check browser availability before running tests."""
    global _BROWSER_AVAILABLE
    _BROWSER_AVAILABLE = _check_browser_available()

    if not _BROWSER_AVAILABLE:
        print(
            "\n⚠️  Playwright browser not available. E2E tests will be skipped.\n"
            "   To enable, run:\n"
            "     sudo playwright install-deps chromium\n"
            "     playwright install chromium\n",
            file=sys.stderr,
        )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip all e2e tests if browser isn't available."""
    if not _BROWSER_AVAILABLE:
        skip_marker = pytest.mark.skip(
            reason="Playwright browser not available (missing system deps)"
        )
        for item in items:
            item.add_marker(skip_marker)


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict:
    """Configure browser launch arguments."""
    return {
        "headless": True,
        "args": ["--no-sandbox"],  # Required for CI environments
    }


@pytest.fixture(scope="session")
def browser_context_args() -> dict:
    """Configure browser context."""
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }
