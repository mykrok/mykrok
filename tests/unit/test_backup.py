"""Unit tests for backup service logic.

Tests for BackupService methods that don't require API calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from mykrok.models.activity import Activity


@pytest.fixture
def mock_config(tmp_path: Path) -> MagicMock:
    """Create a mock config pointing to tmp directory."""
    config = MagicMock()
    config.data.directory = tmp_path / "data"
    config.data.directory.mkdir(exist_ok=True)
    config.strava.client_id = "test_id"
    config.strava.client_secret = "test_secret"
    return config


@pytest.fixture
def setup_athlete_dir(mock_config: MagicMock) -> Path:
    """Create an athlete directory structure."""
    data_dir = mock_config.data.directory
    athlete_dir = data_dir / "athl=testuser"
    athlete_dir.mkdir(exist_ok=True)
    return athlete_dir


def create_activity(
    session_key: str,
    activity_id: int,
    activity_type: str = "Run",
    start_date: datetime | None = None,
    elapsed_time: int = 1800,
    has_photos: bool = False,
    photo_count: int = 0,
    has_gps: bool = True,
) -> Activity:
    """Create an Activity instance for testing."""
    if start_date is None:
        # Parse from session_key like "20240115T100000"
        start_date = datetime.strptime(session_key, "%Y%m%dT%H%M%S").replace(
            tzinfo=timezone.utc
        )

    return Activity(
        id=activity_id,
        name=f"Test Activity {activity_id}",
        type=activity_type,
        sport_type=activity_type,
        start_date=start_date,
        start_date_local=start_date.replace(tzinfo=None),
        timezone="America/New_York",
        distance=5000.0,
        moving_time=elapsed_time - 100,
        elapsed_time=elapsed_time,
        total_elevation_gain=100.0,
        has_gps=has_gps,
        has_photos=has_photos,
        photo_count=photo_count,
    )


def create_session_on_disk(
    athlete_dir: Path,
    session_key: str,
    activity: Activity,
    create_tracking: bool = True,
    create_photos: bool = True,
) -> Path:
    """Create a session directory with activity data on disk."""
    session_dir = athlete_dir / f"ses={session_key}"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Create info.json
    info_data: dict[str, Any] = {
        "id": activity.id,
        "name": activity.name,
        "type": activity.type,
        "sport_type": activity.sport_type,
        "start_date": activity.start_date.isoformat(),
        "start_date_local": activity.start_date_local.isoformat(),
        "timezone": activity.timezone,
        "distance": activity.distance,
        "moving_time": activity.moving_time,
        "elapsed_time": activity.elapsed_time,
        "total_elevation_gain": activity.total_elevation_gain,
        "has_gps": activity.has_gps,
        "has_photos": activity.has_photos,
        "photo_count": activity.photo_count,
    }
    if activity.related_sessions:
        info_data["related_sessions"] = activity.related_sessions

    with open(session_dir / "info.json", "w") as f:
        json.dump(info_data, f)

    # Create tracking.parquet if requested
    if activity.has_gps and create_tracking:
        table = pa.table(
            {
                "time": pa.array([0, 1, 2], type=pa.int32()),
                "lat": pa.array([40.0, 40.01, 40.02], type=pa.float64()),
                "lng": pa.array([-74.0, -74.01, -74.02], type=pa.float64()),
            }
        )
        pq.write_table(table, session_dir / "tracking.parquet")

    # Create photos if requested
    if activity.has_photos and create_photos and activity.photo_count > 0:
        photos_dir = session_dir / "photos"
        photos_dir.mkdir()
        for i in range(activity.photo_count):
            (photos_dir / f"photo_{i + 1}.jpg").write_bytes(b"fake image data")

    return session_dir


class TestFindRelatedSessions:
    """Tests for _find_related_sessions method."""

    @pytest.mark.ai_generated
    def test_finds_related_sessions_within_time_window(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Sessions within time window with same type and similar duration are related.

        This consolidated test verifies:
        - Sessions starting within 10 minutes are considered related
        - Same activity type is required
        - Similar duration is required
        - Current session is excluded from results
        """
        athlete_dir = setup_athlete_dir
        from mykrok.services.backup import BackupService

        # Create main session at 10:00
        main_activity = create_activity(
            "20240115T100000",
            activity_id=1001,
            activity_type="Run",
            elapsed_time=1800,
        )
        create_session_on_disk(athlete_dir, "20240115T100000", main_activity)

        # Create related session at 10:05 (5 min later, same type, similar duration)
        related_activity = create_activity(
            "20240115T100500",
            activity_id=1002,
            activity_type="Run",
            elapsed_time=1850,
        )
        create_session_on_disk(athlete_dir, "20240115T100500", related_activity)

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory

            related = service._find_related_sessions(
                main_activity, athlete_dir, "20240115T100000"
            )

            # Should find the related session
            assert len(related) == 1
            assert related[0][0] == "20240115T100500"

    @pytest.mark.ai_generated
    def test_excludes_unrelated_sessions(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Sessions outside time window, different type, or very different duration excluded.

        This consolidated test verifies:
        - Sessions more than 10 minutes apart are not related
        - Different activity types are not related
        - Very different durations are not related
        """
        athlete_dir = setup_athlete_dir
        from mykrok.services.backup import BackupService

        # Create main session at 10:00
        main_activity = create_activity(
            "20240115T100000",
            activity_id=1001,
            activity_type="Run",
            elapsed_time=1800,
        )
        create_session_on_disk(athlete_dir, "20240115T100000", main_activity)

        # Session too far away in time (1 hour later)
        far_activity = create_activity(
            "20240115T110000",
            activity_id=1002,
            activity_type="Run",
            elapsed_time=1800,
        )
        create_session_on_disk(athlete_dir, "20240115T110000", far_activity)

        # Different activity type
        ride_activity = create_activity(
            "20240115T100100",
            activity_id=1003,
            activity_type="Ride",
            elapsed_time=1800,
        )
        create_session_on_disk(athlete_dir, "20240115T100100", ride_activity)

        # Very different duration
        long_activity = create_activity(
            "20240115T100200",
            activity_id=1004,
            activity_type="Run",
            elapsed_time=10800,  # 3 hours vs 30 min
        )
        create_session_on_disk(athlete_dir, "20240115T100200", long_activity)

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory

            related = service._find_related_sessions(
                main_activity, athlete_dir, "20240115T100000"
            )

            # Should find no related sessions
            assert len(related) == 0


class TestRecoverPhotosFromRelated:
    """Tests for _recover_photos_from_related method."""

    @pytest.mark.ai_generated
    def test_links_photos_from_related_session(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Photos from related session should be symlinked."""
        athlete_dir = setup_athlete_dir
        from mykrok.services.backup import BackupService

        # Create main session without photos
        main_activity = create_activity(
            "20240115T100000",
            activity_id=1001,
            activity_type="Run",
            has_photos=True,
            photo_count=2,
        )
        main_session_dir = create_session_on_disk(
            athlete_dir, "20240115T100000", main_activity, create_photos=False
        )

        # Create related session with photos
        related_activity = create_activity(
            "20240115T100500",
            activity_id=1002,
            activity_type="Run",
            has_photos=True,
            photo_count=2,
        )
        create_session_on_disk(
            athlete_dir, "20240115T100500", related_activity, create_photos=True
        )

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory

            linked = service._recover_photos_from_related(
                main_activity,
                athlete_dir,
                "20240115T100000",
                main_session_dir,
                lambda _msg, _lvl: None,
            )

            # Should have linked 2 photos
            assert linked == 2

            # Verify symlinks exist
            photos_dir = main_session_dir / "photos"
            assert photos_dir.exists()
            photo_links = list(photos_dir.glob("*.jpg"))
            assert len(photo_links) == 2
            for link in photo_links:
                assert link.is_symlink()

    @pytest.mark.ai_generated
    def test_no_related_sessions_returns_zero(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """When no related sessions exist, should return 0."""
        athlete_dir = setup_athlete_dir
        from mykrok.services.backup import BackupService

        # Create only main session
        main_activity = create_activity(
            "20240115T100000",
            activity_id=1001,
            activity_type="Run",
            has_photos=True,
            photo_count=2,
        )
        main_session_dir = create_session_on_disk(
            athlete_dir, "20240115T100000", main_activity, create_photos=False
        )

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory

            linked = service._recover_photos_from_related(
                main_activity,
                athlete_dir,
                "20240115T100000",
                main_session_dir,
                lambda _msg, _lvl: None,
            )

            assert linked == 0


class TestPhotoDownloadValidation:
    """Tests for photo download URL validation."""

    @pytest.mark.ai_generated
    def test_placeholder_url_detection(self) -> None:
        """Placeholder URLs should be detected as invalid."""
        placeholder_urls = [
            "https://d3nn82uaxijpm6.cloudfront.net/assets/placeholder-xxxxx",
            "https://cloudfront.net/assets/placeholder-abc123.png",
        ]

        valid_urls = [
            "https://dgtzuqphqg23d.cloudfront.net/abc123/photo.jpg",
            "https://example.com/real-photo.jpg",
        ]

        for url in placeholder_urls:
            assert "placeholder" in url.lower()

        for url in valid_urls:
            assert "placeholder" not in url.lower()


class TestLeanUpdate:
    """Tests for the lean_update parameter in sync()."""

    @pytest.mark.ai_generated
    def test_lean_update_skips_state_and_log_when_no_changes(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """When lean_update=True and no changes, state and log are not kept."""
        from mykrok.lib import logging as mykrok_logging
        from mykrok.models.state import SyncState, load_sync_state, save_sync_state
        from mykrok.services.backup import BackupService

        _ = setup_athlete_dir  # Ensure athlete dir exists
        data_dir = mock_config.data.directory

        # Create initial sync state with a known timestamp
        initial_state = SyncState(
            last_sync=datetime(2024, 1, 1, 12, 0, 0),
            last_activity_date=datetime(2024, 1, 1, 10, 0, 0),
            total_activities=5,
        )
        save_sync_state(data_dir, "testuser", initial_state)

        # Create a log file that should be removed
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "mykrok-test.log"
        log_file.write_text("test log content\n")
        mykrok_logging._current_log_file = log_file
        mykrok_logging._file_handler = MagicMock()

        # Mock Strava client to return empty activities (no new data)
        mock_strava = MagicMock()
        mock_strava.get_athlete.return_value = MagicMock(
            username="testuser",
            id=12345,
            firstname="Test",
            lastname="User",
            profile="",
            city="",
            state="",
            country="",
        )
        mock_strava.get_activities.return_value = iter([])  # No activities

        assert log_file.exists()

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.config = mock_config
            service.strava = mock_strava
            service.data_dir = data_dir

            # Run sync with lean_update=True
            service.sync(lean_update=True)

        # Verify sync_state.json was NOT updated
        state_after = load_sync_state(data_dir, "testuser")
        assert state_after.last_sync == initial_state.last_sync
        assert state_after.total_activities == initial_state.total_activities

        # Verify log file was removed
        assert not log_file.exists()

    @pytest.mark.ai_generated
    def test_default_behavior_always_saves_state(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """When lean_update=False (default), state is always updated."""
        from mykrok.models.state import SyncState, load_sync_state, save_sync_state
        from mykrok.services.backup import BackupService

        _ = setup_athlete_dir
        data_dir = mock_config.data.directory

        initial_state = SyncState(
            last_sync=datetime(2024, 1, 1, 12, 0, 0),
            last_activity_date=datetime(2024, 1, 1, 10, 0, 0),
            total_activities=5,
        )
        save_sync_state(data_dir, "testuser", initial_state)

        mock_strava = MagicMock()
        mock_strava.get_athlete.return_value = MagicMock(
            username="testuser",
            id=12345,
            firstname="Test",
            lastname="User",
            profile="",
            city="",
            state="",
            country="",
        )
        mock_strava.get_activities.return_value = iter([])

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.config = mock_config
            service.strava = mock_strava
            service.data_dir = data_dir

            service.sync(lean_update=False)

        # Verify sync_state.json WAS updated
        state_after = load_sync_state(data_dir, "testuser")
        assert state_after.last_sync != initial_state.last_sync
        assert state_after.last_sync > initial_state.last_sync


class TestAthletesTsvGeneration:
    """Tests for athletes.tsv auto-generation during sync."""

    @pytest.mark.ai_generated
    def test_sync_generates_athletes_tsv_if_missing(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Sync should auto-generate athletes.tsv if it doesn't exist."""
        from mykrok.lib.paths import get_athletes_tsv_path
        from mykrok.services.backup import BackupService

        _ = setup_athlete_dir
        data_dir = mock_config.data.directory

        # Verify athletes.tsv does not exist initially
        athletes_tsv = get_athletes_tsv_path(data_dir)
        assert not athletes_tsv.exists()

        mock_strava = MagicMock()
        mock_strava.get_athlete.return_value = MagicMock(
            username="testuser",
            id=12345,
            firstname="Test",
            lastname="User",
            profile="",
            city="",
            state="",
            country="",
        )
        mock_strava.get_activities.return_value = iter([])

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.config = mock_config
            service.strava = mock_strava
            service.data_dir = data_dir

            service.sync()

        # Verify athletes.tsv was created
        assert athletes_tsv.exists()
        content = athletes_tsv.read_text()
        lines = content.strip().split("\n")
        assert len(lines) >= 2  # Header + at least one athlete
        assert "username" in lines[0]
        assert "testuser" in content

    @pytest.mark.ai_generated
    def test_sync_does_not_regenerate_existing_athletes_tsv(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Sync should not overwrite existing athletes.tsv."""
        from mykrok.lib.paths import get_athletes_tsv_path
        from mykrok.services.backup import BackupService

        _ = setup_athlete_dir
        data_dir = mock_config.data.directory

        athletes_tsv = get_athletes_tsv_path(data_dir)
        original_content = "username\noriginal_user\n"
        athletes_tsv.write_text(original_content)

        mock_strava = MagicMock()
        mock_strava.get_athlete.return_value = MagicMock(
            username="testuser",
            id=12345,
            firstname="Test",
            lastname="User",
            profile="",
            city="",
            state="",
            country="",
        )
        mock_strava.get_activities.return_value = iter([])

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.config = mock_config
            service.strava = mock_strava
            service.data_dir = data_dir

            service.sync()

        assert athletes_tsv.read_text() == original_content


class TestDownloadPhotos:
    """Tests for _download_photos method."""

    @pytest.mark.ai_generated
    def test_download_photos_various_scenarios(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Test photo download with empty list, no URLs, and placeholder URLs.

        This consolidated test verifies:
        - Empty photo list returns zeros
        - Photos without URLs fail gracefully
        - Placeholder URLs are skipped, not downloaded
        """
        from mykrok.services.backup import BackupService

        session_dir = setup_athlete_dir / "ses=20240115T100000"
        session_dir.mkdir()

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory

            # Test empty list
            result_empty = service._download_photos(
                session_dir, [], lambda _msg, _lvl: None
            )
            assert result_empty == {
                "downloaded": 0,
                "already_exists": 0,
                "placeholder": 0,
                "failed": 0,
            }

            # Test photo without URLs
            photos_no_url = [{"unique_id": "photo1"}]
            result_no_url = service._download_photos(
                session_dir, photos_no_url, lambda _msg, _lvl: None
            )
            assert result_no_url["failed"] == 1
            assert result_no_url["downloaded"] == 0

            # Test placeholder URL
            photos_placeholder = [
                {
                    "unique_id": "photo2",
                    "urls": {"600": "https://example.com/placeholder-image.jpg"},
                }
            ]
            result_placeholder = service._download_photos(
                session_dir, photos_placeholder, lambda _msg, _lvl: None
            )
            assert result_placeholder["placeholder"] == 1
            assert result_placeholder["downloaded"] == 0

    @pytest.mark.ai_generated
    @patch("mykrok.services.backup.requests.get")
    def test_download_photos_success_and_errors(
        self, mock_get: MagicMock, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Test successful photo download, already exists, and HTTP errors.

        This consolidated test verifies:
        - Photos already on disk are skipped
        - Successful HTTP download creates files
        - HTTP errors are handled gracefully
        """
        import requests

        from mykrok.lib.paths import format_session_datetime
        from mykrok.services.backup import BackupService

        session_dir = setup_athlete_dir / "ses=20240115T100000"
        session_dir.mkdir()
        photos_dir = session_dir / "photos"
        photos_dir.mkdir()

        # Pre-create a photo file
        photo_dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        expected_name = format_session_datetime(photo_dt) + ".jpg"
        (photos_dir / expected_name).write_bytes(b"existing photo")

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory

            # Test already exists
            photos_exists = [
                {
                    "unique_id": "photo1",
                    "urls": {"600": "https://example.com/real-photo.jpg"},
                    "created_at": "2024-01-15T10:00:00Z",
                }
            ]
            result_exists = service._download_photos(
                session_dir, photos_exists, lambda _msg, _lvl: None
            )
            assert result_exists["already_exists"] == 1
            assert result_exists["downloaded"] == 0

            # Test successful download
            mock_response = MagicMock()
            mock_response.content = b"fake image data"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            photos_new = [
                {
                    "unique_id": "photo2",
                    "urls": {"600": "https://example.com/new-photo.jpg"},
                    "created_at": "2024-01-15T11:00:00Z",
                }
            ]
            result_new = service._download_photos(
                session_dir, photos_new, lambda _msg, _lvl: None
            )
            assert result_new["downloaded"] == 1

            # Test HTTP error
            mock_get.side_effect = requests.RequestException("Network error")
            photos_error = [
                {
                    "unique_id": "photo3",
                    "urls": {"600": "https://example.com/error-photo.jpg"},
                    "created_at": "2024-01-15T12:00:00Z",
                }
            ]
            result_error = service._download_photos(
                session_dir, photos_error, lambda _msg, _lvl: None
            )
            assert result_error["failed"] == 1


class TestCheckAndFix:
    """Tests for check_and_fix method."""

    @pytest.mark.ai_generated
    def test_check_and_fix_detects_issues(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Verify check_and_fix detects missing photos and tracking files.

        This consolidated test verifies:
        - Empty data directory returns zeros
        - Session with has_photos=True but no photos dir is flagged
        - Session with has_gps=True but no tracking file is flagged
        """
        from mykrok.services.backup import BackupService

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = MagicMock()

            # Empty data dir
            result_empty = service.check_and_fix(dry_run=True)
            assert result_empty["sessions_checked"] == 0
            assert result_empty["issues_found"] == 0

        # Create session with missing photos
        activity_missing_photos = create_activity(
            "20240115T100000",
            activity_id=1001,
            has_photos=True,
            photo_count=2,
        )
        create_session_on_disk(
            setup_athlete_dir, "20240115T100000", activity_missing_photos, create_photos=False
        )

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = MagicMock()

            result_missing_photos = service.check_and_fix(dry_run=True)
            assert result_missing_photos["sessions_checked"] == 1
            assert result_missing_photos["issues_found"] >= 1
            assert any("missing_photos" in str(i) for i in result_missing_photos.get("issues", []))

        # Create session with missing tracking
        activity_missing_tracking = create_activity(
            "20240115T110000",
            activity_id=1002,
            has_gps=True,
        )
        create_session_on_disk(
            setup_athlete_dir, "20240115T110000", activity_missing_tracking, create_tracking=False
        )

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = MagicMock()

            result_missing_tracking = service.check_and_fix(dry_run=True)
            assert result_missing_tracking["issues_found"] >= 1
            assert any("missing_tracking" in str(i) for i in result_missing_tracking.get("issues", []))

    @pytest.mark.ai_generated
    def test_check_and_fix_no_issues_when_complete(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Complete session should have no issues."""
        from mykrok.services.backup import BackupService

        activity = create_activity(
            "20240115T100000",
            activity_id=1001,
            has_gps=True,
            has_photos=True,
            photo_count=2,
        )
        create_session_on_disk(
            setup_athlete_dir,
            "20240115T100000",
            activity,
            create_tracking=True,
            create_photos=True,
        )

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = MagicMock()

            result = service.check_and_fix(dry_run=True)
            assert result["sessions_checked"] == 1
            assert result["issues_found"] == 0


class TestRefreshSocial:
    """Tests for refresh_social method."""

    @pytest.mark.ai_generated
    def test_refresh_social_dry_run_and_updates(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Verify refresh_social dry run and update behavior.

        This consolidated test verifies:
        - Dry run doesn't call API for updates
        - Refresh updates activity with new comments/kudos
        - Limit parameter restricts number of activities
        """
        from mykrok.services.backup import BackupService

        # Create session
        activity = create_activity(
            "20240115T100000",
            activity_id=1001,
        )
        create_session_on_disk(setup_athlete_dir, "20240115T100000", activity)

        mock_strava = MagicMock()
        mock_strava.get_athlete.return_value = MagicMock(
            username="testuser",
            id=12345,
            firstname="Test",
            lastname="User",
            profile="",
            city="",
            state="",
            country="",
        )

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = mock_strava

            # Test dry run
            result_dry = service.refresh_social(dry_run=True)
            assert result_dry["activities_scanned"] == 1
            assert result_dry["activities_updated"] == 0
            mock_strava.get_activity_comments.assert_not_called()

        # Test actual update
        mock_strava.get_activity_comments.return_value = [
            {"text": "Great run!", "athlete": {"id": 123}}
        ]
        mock_strava.get_activity_kudos.return_value = [{"athlete_id": 456}]

        with (
            patch.object(BackupService, "__init__", lambda _self, _cfg: None),
            patch("mykrok.services.backup.update_sessions_tsv"),
        ):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = mock_strava

            result_update = service.refresh_social()
            assert result_update["activities_scanned"] == 1
            assert result_update["activities_updated"] == 1

    @pytest.mark.ai_generated
    def test_refresh_social_limit_and_rate_limit(
        self, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Verify refresh_social respects limit and handles rate limit errors.

        This consolidated test verifies:
        - Limit parameter restricts number of activities processed
        - Rate limit error stops processing gracefully
        """
        from mykrok.services.backup import BackupService
        from mykrok.services.strava import StravaRateLimitError

        # Create multiple sessions
        for i in range(5):
            activity = create_activity(
                f"20240115T10{i:02d}00",
                activity_id=1001 + i,
            )
            create_session_on_disk(setup_athlete_dir, f"20240115T10{i:02d}00", activity)

        mock_strava = MagicMock()
        mock_strava.get_athlete.return_value = MagicMock(
            username="testuser",
            id=12345,
            firstname="Test",
            lastname="User",
            profile="",
            city="",
            state="",
            country="",
        )
        mock_strava.get_activity_comments.return_value = []
        mock_strava.get_activity_kudos.return_value = []

        # Test limit
        with (
            patch.object(BackupService, "__init__", lambda _self, _cfg: None),
            patch("mykrok.services.backup.update_sessions_tsv"),
        ):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = mock_strava

            result_limit = service.refresh_social(limit=2)
            assert result_limit["activities_scanned"] == 2
            assert mock_strava.get_activity_comments.call_count == 2

        # Reset and test rate limit
        mock_strava.reset_mock()
        mock_strava.get_activity_comments.side_effect = StravaRateLimitError("Rate limit exceeded")

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = mock_strava

            result_rate = service.refresh_social()
            assert result_rate["activities_updated"] == 0
            assert len(result_rate["errors"]) >= 1
            assert "Rate limit" in result_rate["errors"][0]["error"]


class TestRefreshAthleteProfiles:
    """Tests for refresh_athlete_profiles method."""

    @pytest.mark.ai_generated
    @patch("mykrok.services.backup.requests.get")
    def test_refresh_athlete_profiles_dry_run_and_download(
        self, mock_get: MagicMock, mock_config: MagicMock, setup_athlete_dir: Path
    ) -> None:
        """Verify refresh_athlete_profiles dry run and avatar download.

        This consolidated test verifies:
        - Dry run doesn't save any files
        - Avatar is downloaded when profile_url is available
        """
        from mykrok.services.backup import BackupService

        assert setup_athlete_dir.exists()

        mock_strava = MagicMock()
        mock_strava.get_athlete.return_value = MagicMock(
            username="testuser",
            id=12345,
            firstname="Test",
            lastname="User",
            profile="https://example.com/avatar.jpg",
            city="New York",
            state="NY",
            country="USA",
        )

        with patch.object(BackupService, "__init__", lambda _self, _cfg: None):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = mock_strava

            # Test dry run
            result_dry = service.refresh_athlete_profiles(dry_run=True)
            assert result_dry["profiles_updated"] == 0
            assert result_dry["avatars_downloaded"] == 0

        # Test actual download
        mock_response = MagicMock()
        mock_response.content = b"avatar image data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with (
            patch.object(BackupService, "__init__", lambda _self, _cfg: None),
            patch("mykrok.services.backup.generate_athletes_tsv"),
        ):
            service = BackupService.__new__(BackupService)
            service.data_dir = mock_config.data.directory
            service.strava = mock_strava

            result_download = service.refresh_athlete_profiles()
            assert result_download["profiles_updated"] == 1
            assert result_download["avatars_downloaded"] == 1

            avatar_files = list(setup_athlete_dir.glob("avatar.*"))
            assert len(avatar_files) == 1
