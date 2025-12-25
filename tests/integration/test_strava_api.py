"""Integration tests for Strava API (mocked)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mykrok.config import Config, DataConfig, StravaConfig, SyncConfig


@pytest.fixture
def mock_config(tmp_path: Path) -> Config:
    """Create a mock configuration for testing."""
    return Config(
        strava=StravaConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_expires_at=int((datetime.now() + timedelta(hours=1)).timestamp()),
        ),
        data=DataConfig(directory=tmp_path / "data"),
        sync=SyncConfig(photos=True, streams=True, comments=True),
    )


@pytest.fixture
def sample_strava_activity() -> dict:
    """Sample activity response from Strava API."""
    return {
        "id": 12345678901,
        "name": "Morning Run",
        "description": "Easy recovery run",
        "type": "Run",
        "sport_type": "Run",
        "start_date": datetime(2025, 12, 18, 6, 30, 0),
        "start_date_local": datetime(2025, 12, 18, 7, 30, 0),
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
        "start_latlng": [40.7128, -74.0060],
    }


@pytest.fixture
def sample_strava_streams() -> dict:
    """Sample stream response from Strava API."""
    return {
        "time": {"data": [0, 1, 2, 3, 4, 5], "series_type": "time", "resolution": "high"},
        "latlng": {
            "data": [
                [40.7128, -74.0060],
                [40.7129, -74.0059],
                [40.7130, -74.0058],
                [40.7131, -74.0057],
                [40.7132, -74.0056],
                [40.7133, -74.0055],
            ],
            "series_type": "latlng",
            "resolution": "high",
        },
        "altitude": {"data": [10.0, 10.2, 10.5, 10.8, 11.0, 11.2], "series_type": "altitude"},
        "heartrate": {"data": [135, 138, 140, 142, 145, 148], "series_type": "heartrate"},
        "distance": {"data": [0, 10, 20, 30, 40, 50], "series_type": "distance"},
    }


@pytest.mark.ai_generated
@pytest.mark.integration
class TestStravaClientMocked:
    """Integration tests for Strava API client with mocked responses."""

    def test_get_athlete(self, mock_config: Config) -> None:
        """Test fetching athlete profile."""
        from mykrok.services.strava import StravaClient

        mock_athlete = MagicMock()
        mock_athlete.id = 12345
        mock_athlete.username = "testathlete"
        mock_athlete.firstname = "Test"
        mock_athlete.lastname = "Athlete"
        mock_athlete.profile = "https://example.com/profile.jpg"
        mock_athlete.city = "Berlin"
        mock_athlete.country = "Germany"
        mock_athlete.bikes = []
        mock_athlete.shoes = []

        with patch("mykrok.services.strava.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.get_athlete.return_value = mock_athlete
            MockClient.return_value = mock_client_instance

            client = StravaClient(mock_config)
            client._client = mock_client_instance

            athlete = client.get_athlete()

            assert athlete.id == 12345
            assert athlete.username == "testathlete"

    def test_get_activities(self, mock_config: Config, sample_strava_activity: dict) -> None:
        """Test fetching activities list."""
        from mykrok.services.strava import StravaClient

        mock_activity = MagicMock()
        for key, value in sample_strava_activity.items():
            setattr(mock_activity, key, value)

        with patch("mykrok.services.strava.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.get_activities.return_value = iter([mock_activity])
            MockClient.return_value = mock_client_instance

            client = StravaClient(mock_config)
            client._client = mock_client_instance

            activities = list(client.get_activities(limit=10))

            assert len(activities) == 1
            assert activities[0].id == 12345678901
            assert activities[0].name == "Morning Run"

    def test_get_activity_streams(self, mock_config: Config, sample_strava_streams: dict) -> None:
        """Test fetching activity streams."""
        from mykrok.services.strava import StravaClient

        # Create mock stream objects
        mock_streams = {}
        for stream_type, stream_data in sample_strava_streams.items():
            mock_stream = MagicMock()
            mock_stream.data = stream_data["data"]
            mock_streams[stream_type] = mock_stream

        with patch("mykrok.services.strava.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.get_activity_streams.return_value = mock_streams
            MockClient.return_value = mock_client_instance

            client = StravaClient(mock_config)
            client._client = mock_client_instance

            streams = client.get_activity_streams(12345678901)

            assert "time" in streams
            assert "latlng" in streams
            assert "heartrate" in streams
            assert len(streams["time"]) == 6

    def test_get_activity_comments(self, mock_config: Config) -> None:
        """Test fetching activity comments."""
        from mykrok.services.strava import StravaClient

        mock_comment = MagicMock()
        mock_comment.id = 1001
        mock_comment.text = "Great run!"
        mock_comment.created_at = datetime(2025, 12, 18, 8, 0, 0)
        mock_comment.athlete = MagicMock()
        mock_comment.athlete.id = 54321
        mock_comment.athlete.firstname = "Jane"
        mock_comment.athlete.lastname = "Doe"

        with patch("mykrok.services.strava.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.get_activity_comments.return_value = [mock_comment]
            MockClient.return_value = mock_client_instance

            client = StravaClient(mock_config)
            client._client = mock_client_instance

            comments = client.get_activity_comments(12345678901)

            assert len(comments) == 1
            assert comments[0]["text"] == "Great run!"
            assert comments[0]["athlete_firstname"] == "Jane"

    def test_get_activity_kudos(self, mock_config: Config) -> None:
        """Test fetching activity kudos."""
        from mykrok.services.strava import StravaClient

        mock_kudo = MagicMock()
        mock_kudo.id = 54321
        mock_kudo.firstname = "John"
        mock_kudo.lastname = "Smith"

        with patch("mykrok.services.strava.Client") as MockClient:
            mock_client_instance = MagicMock()
            mock_client_instance.get_activity_kudos.return_value = [mock_kudo]
            MockClient.return_value = mock_client_instance

            client = StravaClient(mock_config)
            client._client = mock_client_instance

            kudos = client.get_activity_kudos(12345678901)

            assert len(kudos) == 1
            assert kudos[0]["firstname"] == "John"


@pytest.mark.ai_generated
@pytest.mark.integration
class TestBackupServiceMocked:
    """Integration tests for backup service with mocked Strava client."""

    def test_sync_creates_activity_files(
        self,
        mock_config: Config,
        sample_strava_activity: dict,
        sample_strava_streams: dict,
    ) -> None:
        """Test that sync creates proper activity files."""
        from mykrok.services.backup import BackupService

        # Create mock athlete
        mock_athlete = MagicMock()
        mock_athlete.id = 12345
        mock_athlete.username = "testathlete"
        mock_athlete.firstname = "Test"
        mock_athlete.lastname = "Athlete"
        mock_athlete.profile = None
        mock_athlete.city = None
        mock_athlete.country = None
        mock_athlete.bikes = []
        mock_athlete.shoes = []

        # Create mock activity
        mock_activity = MagicMock()
        for key, value in sample_strava_activity.items():
            setattr(mock_activity, key, value)
        # Add timedelta objects for time fields
        mock_activity.moving_time = timedelta(seconds=1800)
        mock_activity.elapsed_time = timedelta(seconds=1850)

        # Create mock streams
        mock_streams = {}
        for stream_type, stream_data in sample_strava_streams.items():
            mock_stream = MagicMock()
            mock_stream.data = stream_data["data"]
            mock_streams[stream_type] = mock_stream

        with patch("mykrok.services.backup.StravaClient") as MockStravaClient:
            mock_strava = MagicMock()
            mock_strava.get_athlete.return_value = mock_athlete
            mock_strava.get_activities.return_value = iter([mock_activity])
            mock_strava.get_activity.return_value = mock_activity
            mock_strava.get_activity_streams.return_value = {
                k: v["data"] for k, v in sample_strava_streams.items()
            }
            mock_strava.get_activity_photos.return_value = []
            mock_strava.get_activity_comments.return_value = []
            mock_strava.get_activity_kudos.return_value = []
            mock_strava.get_athlete_gear.return_value = []
            MockStravaClient.return_value = mock_strava

            service = BackupService(mock_config)
            service.strava = mock_strava

            result = service.sync(limit=1)

            assert result["activities_synced"] == 1
            assert result["activities_new"] == 1
            assert result["athlete"] == "testathlete"

            # Verify files were created
            data_dir = mock_config.data.directory
            athlete_dir = data_dir / "athl=testathlete"
            assert athlete_dir.exists()

            # Check for sessions.tsv
            sessions_file = athlete_dir / "sessions.tsv"
            assert sessions_file.exists()

    def test_sync_dry_run_no_files(
        self,
        mock_config: Config,
        sample_strava_activity: dict,
    ) -> None:
        """Test that dry run doesn't create files."""
        from mykrok.services.backup import BackupService

        # Create mock athlete
        mock_athlete = MagicMock()
        mock_athlete.id = 12345
        mock_athlete.username = "testathlete"
        mock_athlete.firstname = "Test"
        mock_athlete.lastname = "Athlete"
        mock_athlete.profile = None
        mock_athlete.city = None
        mock_athlete.country = None
        mock_athlete.bikes = []
        mock_athlete.shoes = []

        # Create mock activity
        mock_activity = MagicMock()
        for key, value in sample_strava_activity.items():
            setattr(mock_activity, key, value)
        mock_activity.moving_time = timedelta(seconds=1800)
        mock_activity.elapsed_time = timedelta(seconds=1850)

        with patch("mykrok.services.backup.StravaClient") as MockStravaClient:
            mock_strava = MagicMock()
            mock_strava.get_athlete.return_value = mock_athlete
            mock_strava.get_activities.return_value = iter([mock_activity])
            mock_strava.get_activity.return_value = mock_activity
            mock_strava.get_athlete_gear.return_value = []
            MockStravaClient.return_value = mock_strava

            service = BackupService(mock_config)
            service.strava = mock_strava

            result = service.sync(limit=1, dry_run=True)

            # In dry_run, activities_synced counts processed activities
            assert result["activities_synced"] >= 0

            # Verify no session directories were created
            data_dir = mock_config.data.directory
            athlete_dir = data_dir / "athl=testathlete"
            # Athlete dir shouldn't have session subdirectories
            session_dirs = list(athlete_dir.glob("ses=*")) if athlete_dir.exists() else []
            assert len(session_dirs) == 0

    def test_refresh_social_updates_kudos_and_comments(
        self,
        mock_config: Config,
        sample_strava_activity: dict,
        sample_strava_streams: dict,
    ) -> None:
        """Test that refresh_social updates kudos and comments for existing activities."""
        from mykrok.services.backup import BackupService

        # Create mock athlete
        mock_athlete = MagicMock()
        mock_athlete.id = 12345
        mock_athlete.username = "testathlete"
        mock_athlete.firstname = "Test"
        mock_athlete.lastname = "Athlete"
        mock_athlete.profile = None
        mock_athlete.city = None
        mock_athlete.country = None
        mock_athlete.bikes = []
        mock_athlete.shoes = []

        # Create mock activity
        mock_activity = MagicMock()
        for key, value in sample_strava_activity.items():
            setattr(mock_activity, key, value)
        mock_activity.moving_time = timedelta(seconds=1800)
        mock_activity.elapsed_time = timedelta(seconds=1850)

        with patch("mykrok.services.backup.StravaClient") as MockStravaClient:
            mock_strava = MagicMock()
            mock_strava.get_athlete.return_value = mock_athlete
            mock_strava.get_activities.return_value = iter([mock_activity])
            mock_strava.get_activity.return_value = mock_activity
            mock_strava.get_activity_streams.return_value = {
                k: v["data"] for k, v in sample_strava_streams.items()
            }
            mock_strava.get_activity_photos.return_value = []
            mock_strava.get_activity_comments.return_value = []
            mock_strava.get_activity_kudos.return_value = []
            mock_strava.get_athlete_gear.return_value = []
            MockStravaClient.return_value = mock_strava

            service = BackupService(mock_config)
            service.strava = mock_strava

            # First, sync to create activity files
            result = service.sync(limit=1)
            assert result["activities_synced"] == 1

            # Now set up new kudos/comments for refresh
            mock_strava.get_activity_comments.return_value = [
                {
                    "id": 1001,
                    "text": "Great run!",
                    "created_at": "2025-12-18T08:00:00",
                    "athlete_id": 54321,
                    "athlete_firstname": "Jane",
                    "athlete_lastname": "Doe",
                },
            ]
            mock_strava.get_activity_kudos.return_value = [
                {"athlete_id": 99999, "firstname": "John", "lastname": "Smith"},
                {"athlete_id": 88888, "firstname": "Bob", "lastname": "Jones"},
            ]

            # Run refresh_social
            refresh_result = service.refresh_social()

            assert refresh_result["activities_scanned"] == 1
            assert refresh_result["activities_updated"] == 1
            assert refresh_result["errors"] == []

            # Verify the API was called to get comments and kudos
            mock_strava.get_activity_comments.assert_called()
            mock_strava.get_activity_kudos.assert_called()

    def test_refresh_social_dry_run_no_changes(
        self,
        mock_config: Config,
        sample_strava_activity: dict,
        sample_strava_streams: dict,
    ) -> None:
        """Test that refresh_social with dry_run doesn't modify files."""
        from mykrok.services.backup import BackupService

        # Create mock athlete
        mock_athlete = MagicMock()
        mock_athlete.id = 12345
        mock_athlete.username = "testathlete"
        mock_athlete.firstname = "Test"
        mock_athlete.lastname = "Athlete"
        mock_athlete.profile = None
        mock_athlete.city = None
        mock_athlete.country = None
        mock_athlete.bikes = []
        mock_athlete.shoes = []

        # Create mock activity
        mock_activity = MagicMock()
        for key, value in sample_strava_activity.items():
            setattr(mock_activity, key, value)
        mock_activity.moving_time = timedelta(seconds=1800)
        mock_activity.elapsed_time = timedelta(seconds=1850)

        with patch("mykrok.services.backup.StravaClient") as MockStravaClient:
            mock_strava = MagicMock()
            mock_strava.get_athlete.return_value = mock_athlete
            mock_strava.get_activities.return_value = iter([mock_activity])
            mock_strava.get_activity.return_value = mock_activity
            mock_strava.get_activity_streams.return_value = {
                k: v["data"] for k, v in sample_strava_streams.items()
            }
            mock_strava.get_activity_photos.return_value = []
            mock_strava.get_activity_comments.return_value = []
            mock_strava.get_activity_kudos.return_value = []
            mock_strava.get_athlete_gear.return_value = []
            MockStravaClient.return_value = mock_strava

            service = BackupService(mock_config)
            service.strava = mock_strava

            # First, sync to create activity files
            result = service.sync(limit=1)
            assert result["activities_synced"] == 1

            # Run refresh_social with dry_run=True
            refresh_result = service.refresh_social(dry_run=True)

            assert refresh_result["activities_scanned"] == 1
            assert refresh_result["activities_updated"] == 0  # No updates in dry run

            # Verify the API was NOT called to get comments/kudos (dry run skips)
            # Reset call counts after sync
            mock_strava.get_activity_comments.reset_mock()
            mock_strava.get_activity_kudos.reset_mock()

            refresh_result = service.refresh_social(dry_run=True)
            mock_strava.get_activity_comments.assert_not_called()
            mock_strava.get_activity_kudos.assert_not_called()

    def test_refresh_social_respects_limit(
        self,
        mock_config: Config,
        sample_strava_activity: dict,
        sample_strava_streams: dict,  # noqa: ARG002
    ) -> None:
        """Test that refresh_social respects limit parameter."""
        from mykrok.services.backup import BackupService

        # Create mock athlete
        mock_athlete = MagicMock()
        mock_athlete.id = 12345
        mock_athlete.username = "testathlete"
        mock_athlete.firstname = "Test"
        mock_athlete.lastname = "Athlete"
        mock_athlete.profile = None
        mock_athlete.city = None
        mock_athlete.country = None
        mock_athlete.bikes = []
        mock_athlete.shoes = []

        # Create two mock activities with different dates
        activities = []
        for i, day in enumerate([18, 17]):
            mock_activity = MagicMock()
            for key, value in sample_strava_activity.items():
                setattr(mock_activity, key, value)
            mock_activity.id = 12345678901 + i
            mock_activity.name = f"Run {i+1}"
            mock_activity.start_date = datetime(2025, 12, day, 6, 30, 0)
            mock_activity.start_date_local = datetime(2025, 12, day, 7, 30, 0)
            mock_activity.moving_time = timedelta(seconds=1800)
            mock_activity.elapsed_time = timedelta(seconds=1850)
            activities.append(mock_activity)

        with patch("mykrok.services.backup.StravaClient") as MockStravaClient:
            mock_strava = MagicMock()
            mock_strava.get_athlete.return_value = mock_athlete
            mock_strava.get_activities.return_value = iter(activities)
            mock_strava.get_activity.side_effect = activities
            mock_strava.get_activity_streams.return_value = {}
            mock_strava.get_activity_photos.return_value = []
            mock_strava.get_activity_comments.return_value = []
            mock_strava.get_activity_kudos.return_value = []
            mock_strava.get_athlete_gear.return_value = []
            MockStravaClient.return_value = mock_strava

            service = BackupService(mock_config)
            service.strava = mock_strava

            # First, sync both activities
            result = service.sync(limit=2)
            assert result["activities_synced"] == 2

            # Reset mock for refresh
            mock_strava.get_activity_comments.reset_mock()

            # Run refresh_social with limit=1
            refresh_result = service.refresh_social(limit=1)

            assert refresh_result["activities_scanned"] == 1
            assert refresh_result["activities_updated"] == 1
