"""Pytest configuration for e2e tests.

Configures playwright for headless browser testing.
"""

from __future__ import annotations

import pytest


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
