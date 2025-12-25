"""Shared pytest fixtures for mykrok tests."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_activity() -> dict[str, Any]:
    """Return a sample Strava activity as a dictionary."""
    return {
        "id": 12345678901,
        "name": "Morning Run",
        "description": "Easy recovery run",
        "type": "Run",
        "sport_type": "Run",
        "start_date": "2025-12-18T06:30:00Z",
        "start_date_local": "2025-12-18T07:30:00",
        "timezone": "(GMT+01:00) Europe/Berlin",
        "distance": 5234.5,
        "moving_time": 1800,
        "elapsed_time": 1850,
        "total_elevation_gain": 45.2,
        "calories": 350,
        "average_speed": 2.91,
        "max_speed": 3.85,
        "average_heartrate": 142.5,
        "max_heartrate": 165,
        "average_cadence": 85.0,
        "gear_id": "g12345",
        "device_name": "Garmin Forerunner 265",
        "trainer": False,
        "commute": False,
        "private": False,
        "kudos_count": 5,
        "comment_count": 2,
        "athlete_count": 1,
        "achievement_count": 3,
        "pr_count": 1,
    }


@pytest.fixture
def sample_stream_data() -> dict[str, list[float | int]]:
    """Return sample GPS/sensor stream data."""
    # 10 data points representing ~30 seconds of running
    return {
        "time": [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 21.0, 24.0, 27.0],
        "latlng": [
            [40.7128, -74.0060],
            [40.7129, -74.0059],
            [40.7130, -74.0058],
            [40.7131, -74.0057],
            [40.7132, -74.0056],
            [40.7133, -74.0055],
            [40.7134, -74.0054],
            [40.7135, -74.0053],
            [40.7136, -74.0052],
            [40.7137, -74.0051],
        ],
        "altitude": [10.0, 10.2, 10.5, 10.8, 11.0, 11.2, 11.5, 11.8, 12.0, 12.2],
        "distance": [0.0, 10.5, 21.0, 31.5, 42.0, 52.5, 63.0, 73.5, 84.0, 94.5],
        "heartrate": [135, 138, 140, 142, 145, 148, 150, 152, 155, 158],
        "cadence": [82, 83, 84, 85, 85, 86, 86, 87, 87, 88],
    }


@pytest.fixture
def sample_athlete() -> dict[str, Any]:
    """Return a sample Strava athlete profile."""
    return {
        "id": 12345,
        "username": "athlete123",
        "firstname": "Test",
        "lastname": "Athlete",
        "profile": "https://example.com/profile.jpg",
        "city": "Berlin",
        "country": "Germany",
    }


@pytest.fixture
def sample_gear() -> list[dict[str, Any]]:
    """Return sample gear items."""
    return [
        {
            "id": "g12345",
            "name": "Asics Gel-Nimbus 25",
            "type": "shoes",
            "brand": "Asics",
            "model": "Gel-Nimbus 25",
            "distance_m": 523400.0,
            "primary": True,
            "retired": False,
        },
        {
            "id": "b67890",
            "name": "Canyon Ultimate CF SL",
            "type": "bike",
            "brand": "Canyon",
            "model": "Ultimate CF SL",
            "distance_m": 12345600.0,
            "primary": True,
            "retired": False,
        },
    ]


@pytest.fixture
def sample_comments() -> list[dict[str, Any]]:
    """Return sample activity comments."""
    return [
        {
            "id": 1001,
            "text": "Great run!",
            "created_at": "2025-12-18T08:00:00Z",
            "athlete_id": 54321,
            "athlete_firstname": "Jane",
            "athlete_lastname": "Doe",
        },
        {
            "id": 1002,
            "text": "Nice pace!",
            "created_at": "2025-12-18T09:30:00Z",
            "athlete_id": 54322,
            "athlete_firstname": "John",
            "athlete_lastname": "Smith",
        },
    ]


@pytest.fixture
def sample_kudos() -> list[dict[str, Any]]:
    """Return sample activity kudos."""
    return [
        {"athlete_id": 54321, "firstname": "Jane", "lastname": "Doe"},
        {"athlete_id": 54322, "firstname": "John", "lastname": "Smith"},
        {"athlete_id": 54323, "firstname": "Alice", "lastname": "Jones"},
    ]


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_config(temp_data_dir: Path) -> dict[str, Any]:
    """Return a mock configuration dictionary."""
    return {
        "strava": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
        },
        "data": {
            "directory": str(temp_data_dir),
        },
        "fittrackee": {
            "url": "https://fittrackee.example.com",
            "email": "test@example.com",
        },
        "sync": {
            "photos": True,
            "streams": True,
            "comments": True,
        },
    }


def write_json_fixture(path: Path, data: dict[str, Any] | list[Any]) -> None:
    """Helper to write JSON fixture files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
