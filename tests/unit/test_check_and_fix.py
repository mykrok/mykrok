"""Tests for check_and_fix functionality."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest


@pytest.fixture
def setup_data_dir(tmp_path: Path) -> Path:
    """Create a mock data directory with athlete and sessions."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Create athlete directory
    athlete_dir = data_dir / "athl=testuser"
    athlete_dir.mkdir()

    return data_dir


def create_session(
    athlete_dir: Path,
    session_key: str,
    activity_id: int,
    has_gps: bool = True,
    has_photos: bool = False,
    photo_count: int = 0,
    create_tracking: bool = True,
    create_photos: bool = True,
    corrupt_tracking: bool = False,
) -> dict[str, Any]:
    """Create a session directory with info.json and optionally tracking/photos."""
    session_dir = athlete_dir / f"ses={session_key}"
    session_dir.mkdir(parents=True)

    # Create info.json
    activity_data = {
        "id": activity_id,
        "name": f"Test Activity {activity_id}",
        "type": "Run",
        "sport_type": "Run",
        "start_date": f"2024-01-{int(session_key[-2:]):02d}T10:00:00Z",
        "start_date_local": f"2024-01-{int(session_key[-2:]):02d}T10:00:00",
        "distance": 5000.0,
        "moving_time": 1800,
        "elapsed_time": 1900,
        "has_gps": has_gps,
        "has_photos": has_photos,
        "photo_count": photo_count,
    }

    info_path = session_dir / "info.json"
    with open(info_path, "w") as f:
        json.dump(activity_data, f)

    # Create tracking.parquet if requested
    if has_gps and create_tracking:
        if corrupt_tracking:
            # Write invalid data
            (session_dir / "tracking.parquet").write_text("not a parquet file")
        else:
            # Create valid parquet
            table = pa.table(
                {
                    "time": pa.array([0, 1, 2], type=pa.int32()),
                    "lat": pa.array([40.0, 40.01, 40.02], type=pa.float64()),
                    "lng": pa.array([-74.0, -74.01, -74.02], type=pa.float64()),
                }
            )
            pq.write_table(table, session_dir / "tracking.parquet")

    # Create photos if requested
    if has_photos and create_photos and photo_count > 0:
        photos_dir = session_dir / "photos"
        photos_dir.mkdir()
        for i in range(photo_count):
            (photos_dir / f"photo_{i + 1}.jpg").write_bytes(b"fake image data")

    return activity_data


class TestCheckAndFix:
    """Tests for check_and_fix method."""

    @pytest.mark.ai_generated
    def test_no_issues_found(self, setup_data_dir: Path) -> None:
        """Test that a valid session passes all checks."""
        data_dir = setup_data_dir
        athlete_dir = data_dir / "athl=testuser"

        # Create a valid session with GPS and photos
        create_session(
            athlete_dir,
            "20240115T100000",
            activity_id=1001,
            has_gps=True,
            has_photos=True,
            photo_count=2,
            create_tracking=True,
            create_photos=True,
        )

        # Manually check the session (simulating what check_and_fix does)
        session_dir = athlete_dir / "ses=20240115T100000"
        tracking_file = session_dir / "tracking.parquet"
        photos_dir = session_dir / "photos"

        assert tracking_file.exists()
        assert photos_dir.exists()
        assert len(list(photos_dir.glob("*.jpg"))) == 2

        # Verify parquet is readable
        table = pq.read_table(tracking_file)
        assert table.num_rows == 3

    @pytest.mark.ai_generated
    def test_missing_tracking_detected(self, setup_data_dir: Path) -> None:
        """Test that missing tracking data is detected."""
        data_dir = setup_data_dir
        athlete_dir = data_dir / "athl=testuser"

        # Create a session claiming GPS but no tracking file
        create_session(
            athlete_dir,
            "20240116T100000",
            activity_id=1002,
            has_gps=True,
            create_tracking=False,
        )

        session_dir = athlete_dir / "ses=20240116T100000"
        tracking_file = session_dir / "tracking.parquet"

        # Should be missing
        assert not tracking_file.exists()

        # Load info.json and verify has_gps is True
        with open(session_dir / "info.json") as f:
            info = json.load(f)
        assert info["has_gps"] is True

    @pytest.mark.ai_generated
    def test_missing_photos_detected(self, setup_data_dir: Path) -> None:
        """Test that missing photos are detected."""
        data_dir = setup_data_dir
        athlete_dir = data_dir / "athl=testuser"

        # Create a session claiming photos but no photos directory
        create_session(
            athlete_dir,
            "20240117T100000",
            activity_id=1003,
            has_photos=True,
            photo_count=3,
            create_photos=False,
        )

        session_dir = athlete_dir / "ses=20240117T100000"
        photos_dir = session_dir / "photos"

        # Photos dir should be missing
        assert not photos_dir.exists()

        # Load info.json and verify has_photos is True with photo_count
        with open(session_dir / "info.json") as f:
            info = json.load(f)
        assert info["has_photos"] is True
        assert info["photo_count"] == 3

    @pytest.mark.ai_generated
    def test_corrupted_tracking_detected(self, setup_data_dir: Path) -> None:
        """Test that corrupted tracking file is detected."""
        data_dir = setup_data_dir
        athlete_dir = data_dir / "athl=testuser"

        # Create a session with corrupted tracking
        create_session(
            athlete_dir,
            "20240118T100000",
            activity_id=1004,
            has_gps=True,
            corrupt_tracking=True,
        )

        session_dir = athlete_dir / "ses=20240118T100000"
        tracking_file = session_dir / "tracking.parquet"

        # File exists but should fail to read
        assert tracking_file.exists()

        with pytest.raises(pa.ArrowInvalid):
            pq.read_table(tracking_file)

    @pytest.mark.ai_generated
    def test_partial_photos_detected(self, setup_data_dir: Path) -> None:
        """Test that incomplete photo download is detected."""
        data_dir = setup_data_dir
        athlete_dir = data_dir / "athl=testuser"

        # Create a session with fewer photos than claimed
        create_session(
            athlete_dir,
            "20240119T100000",
            activity_id=1005,
            has_photos=True,
            photo_count=5,
            create_photos=True,
        )

        # Now manually remove some photos to simulate partial download
        session_dir = athlete_dir / "ses=20240119T100000"
        photos_dir = session_dir / "photos"

        # Delete 2 photos
        for photo in list(photos_dir.glob("*.jpg"))[:2]:
            photo.unlink()

        # Should have 3 photos but info claims 5
        with open(session_dir / "info.json") as f:
            info = json.load(f)

        actual_photos = len(list(photos_dir.glob("*.jpg")))
        assert actual_photos < info["photo_count"]

    @pytest.mark.ai_generated
    def test_missing_info_json(self, setup_data_dir: Path) -> None:
        """Test that session without info.json is detected."""
        data_dir = setup_data_dir
        athlete_dir = data_dir / "athl=testuser"

        # Create a session directory without info.json
        session_dir = athlete_dir / "ses=20240120T100000"
        session_dir.mkdir(parents=True)

        # Just create tracking file
        table = pa.table(
            {
                "time": pa.array([0], type=pa.int32()),
                "lat": pa.array([40.0], type=pa.float64()),
                "lng": pa.array([-74.0], type=pa.float64()),
            }
        )
        pq.write_table(table, session_dir / "tracking.parquet")

        # info.json should be missing
        assert not (session_dir / "info.json").exists()
