"""Unit tests for map photo overlay functionality."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from strava_backup.models.activity import Activity, save_activity
from strava_backup.views.map import _collect_geotagged_photos, generate_map


@pytest.mark.ai_generated
class TestCollectGeotaggedPhotos:
    """Tests for _collect_geotagged_photos function."""

    def test_collect_photos_with_location(self, temp_data_dir: Path) -> None:
        """Test collecting photos that have GPS coordinates."""
        # Create an activity with geotagged photos
        activity = Activity(
            id=12345,
            name="Morning Run",
            type="Run",
            sport_type="Run",
            start_date=datetime(2025, 1, 15, 8, 0, 0),
            start_date_local=datetime(2025, 1, 15, 8, 0, 0),
            timezone="America/New_York",
            distance=5000.0,
            moving_time=1800,
            elapsed_time=1900,
            has_photos=True,
            photo_count=2,
            photos=[
                {
                    "unique_id": "photo1",
                    "created_at": "2025-01-15T08:15:00Z",
                    "location": [["root", [40.7128, -74.0060]]],  # NYC
                    "urls": {
                        "256": "http://example.com/photo1_256.jpg",
                        "600": "http://example.com/photo1_600.jpg",
                    },
                },
                {
                    "unique_id": "photo2",
                    "created_at": "2025-01-15T08:30:00Z",
                    "location": [["root", [40.7580, -73.9855]]],  # Times Square
                    "urls": {"256": "http://example.com/photo2_256.jpg"},
                },
            ],
        )

        save_activity(temp_data_dir, "testuser", activity)

        # Collect photos
        photos = _collect_geotagged_photos(temp_data_dir)

        assert len(photos) == 2
        assert photos[0]["lat"] == 40.7128
        assert photos[0]["lng"] == -74.0060
        assert photos[0]["activity_name"] == "Morning Run"
        assert photos[0]["activity_type"] == "Run"
        assert "urls" in photos[0]

    def test_skip_photos_without_location(self, temp_data_dir: Path) -> None:
        """Test that photos without GPS coordinates are skipped."""
        activity = Activity(
            id=12346,
            name="Indoor Workout",
            type="Workout",
            sport_type="Workout",
            start_date=datetime(2025, 1, 16, 10, 0, 0),
            start_date_local=datetime(2025, 1, 16, 10, 0, 0),
            timezone="America/New_York",
            distance=0.0,
            moving_time=3600,
            elapsed_time=3600,
            has_photos=True,
            photo_count=1,
            photos=[
                {
                    "unique_id": "photo3",
                    "created_at": "2025-01-16T10:30:00Z",
                    "location": None,  # No location
                    "urls": {"256": "http://example.com/photo3.jpg"},
                },
            ],
        )

        save_activity(temp_data_dir, "testuser", activity)

        photos = _collect_geotagged_photos(temp_data_dir)

        assert len(photos) == 0

    def test_filter_by_date(self, temp_data_dir: Path) -> None:
        """Test date filtering for photo collection."""
        # Activity 1: January
        activity1 = Activity(
            id=12347,
            name="January Run",
            type="Run",
            sport_type="Run",
            start_date=datetime(2025, 1, 10, 8, 0, 0),
            start_date_local=datetime(2025, 1, 10, 8, 0, 0),
            timezone="UTC",
            distance=5000.0,
            moving_time=1800,
            elapsed_time=1900,
            has_photos=True,
            photos=[
                {
                    "unique_id": "p1",
                    "location": [["root", [40.0, -74.0]]],
                    "urls": {"256": "http://a.com/1.jpg"},
                }
            ],
        )

        # Activity 2: March
        activity2 = Activity(
            id=12348,
            name="March Run",
            type="Run",
            sport_type="Run",
            start_date=datetime(2025, 3, 15, 8, 0, 0),
            start_date_local=datetime(2025, 3, 15, 8, 0, 0),
            timezone="UTC",
            distance=5000.0,
            moving_time=1800,
            elapsed_time=1900,
            has_photos=True,
            photos=[
                {
                    "unique_id": "p2",
                    "location": [["root", [41.0, -73.0]]],
                    "urls": {"256": "http://a.com/2.jpg"},
                }
            ],
        )

        save_activity(temp_data_dir, "testuser", activity1)
        save_activity(temp_data_dir, "testuser", activity2)

        # Filter to February onwards
        photos = _collect_geotagged_photos(temp_data_dir, after=datetime(2025, 2, 1))

        assert len(photos) == 1
        assert photos[0]["activity_name"] == "March Run"


@pytest.mark.ai_generated
class TestGenerateMapWithPhotos:
    """Tests for generate_map with photos enabled."""

    def test_generate_map_includes_photo_scripts(self, temp_data_dir: Path) -> None:
        """Test that generated HTML includes photo-related scripts when photos exist."""
        activity = Activity(
            id=12349,
            name="Photo Run",
            type="Run",
            sport_type="Run",
            start_date=datetime(2025, 1, 20, 9, 0, 0),
            start_date_local=datetime(2025, 1, 20, 9, 0, 0),
            timezone="UTC",
            distance=3000.0,
            moving_time=1200,
            elapsed_time=1200,
            has_photos=True,
            photos=[
                {
                    "unique_id": "px",
                    "location": [["root", [42.0, -71.0]]],
                    "urls": {"256": "http://x.com/x.jpg"},
                }
            ],
        )

        save_activity(temp_data_dir, "testuser", activity)

        html = generate_map(temp_data_dir, show_photos=True)

        # Check for markercluster script
        assert "leaflet.markercluster" in html
        # Check for photo data
        assert "photos" in html
        # Check for photo popup CSS
        assert "photo-popup" in html

    def test_generate_map_without_photos_flag(self, temp_data_dir: Path) -> None:
        """Test that photos are not included when show_photos is False."""
        activity = Activity(
            id=12350,
            name="No Photo Run",
            type="Run",
            sport_type="Run",
            start_date=datetime(2025, 1, 21, 9, 0, 0),
            start_date_local=datetime(2025, 1, 21, 9, 0, 0),
            timezone="UTC",
            distance=3000.0,
            moving_time=1200,
            elapsed_time=1200,
            has_photos=True,
            photos=[
                {
                    "unique_id": "py",
                    "location": [["root", [43.0, -70.0]]],
                    "urls": {"256": "http://y.com/y.jpg"},
                }
            ],
        )

        save_activity(temp_data_dir, "testuser", activity)

        html = generate_map(temp_data_dir, show_photos=False)

        # Should have empty photos array
        assert "var photos = []" in html
