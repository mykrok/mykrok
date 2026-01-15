"""Pytest fixtures for CLI integration tests.

These fixtures provide realistic test data for CLI command testing,
using the generate_fixtures module to create consistent, reproducible data.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Generator

# Add e2e fixtures to path for importing generate_fixtures
_fixtures_path = Path(__file__).parent.parent / "e2e" / "fixtures"
if str(_fixtures_path) not in sys.path:
    sys.path.insert(0, str(_fixtures_path))


@pytest.fixture(scope="session")
def cli_runner() -> CliRunner:
    """Create a Click CLI test runner.

    Using session scope since CliRunner is stateless and reusable.
    """
    return CliRunner()


@pytest.fixture
def cli_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Generate realistic fixture data for CLI tests.

    Creates a temporary directory with:
    - Two athletes (alice, bob)
    - 10+ sessions with activities
    - GPS tracks, photos, comments, kudos
    - athletes.tsv and sessions.tsv files

    Uses deterministic seed for reproducibility.
    """
    import random

    from generate_fixtures import generate_fixtures

    # Set seed for reproducibility
    random.seed(42)

    data_dir = tmp_path / "data"
    generate_fixtures(data_dir)

    yield data_dir


@pytest.fixture
def cli_data_dir_with_config(cli_data_dir: Path, tmp_path: Path) -> Path:
    """Data directory with a minimal config file.

    Some commands may require a config file to be present.
    """
    config_path = tmp_path / "config.toml"
    config_path.write_text(f"""\
[data]
directory = "{cli_data_dir}"

[strava]
client_id = "test_client_id"
client_secret = "test_client_secret"
""")
    return cli_data_dir


@pytest.fixture
def cli_env(cli_data_dir: Path, tmp_path: Path) -> dict[str, str]:
    """Environment variables for CLI tests.

    Returns a dict suitable for use with CliRunner's env parameter.
    """
    config_path = tmp_path / "config.toml"
    config_path.write_text(f"""\
[data]
directory = "{cli_data_dir}"

[strava]
client_id = "test_client_id"
client_secret = "test_client_secret"
""")
    return {
        "MYKROK_CONFIG": str(config_path),
        "MYKROK_DATA_DIR": str(cli_data_dir),
    }


def assert_file_exists(path: Path, msg: str = "") -> None:
    """Assert that a file exists."""
    assert path.exists(), f"Expected file to exist: {path}. {msg}"


def assert_file_contains(path: Path, substring: str, msg: str = "") -> None:
    """Assert that a file contains a substring."""
    content = path.read_text()
    assert substring in content, f"Expected '{substring}' in {path}. {msg}"


def count_lines(path: Path, skip_header: bool = True) -> int:
    """Count lines in a file, optionally skipping header."""
    lines = path.read_text().strip().split("\n")
    if skip_header and len(lines) > 0:
        return len(lines) - 1
    return len(lines)
