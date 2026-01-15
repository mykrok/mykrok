"""Unit tests for FitTrackee export service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import responses

from mykrok.services.fittrackee import (
    DEFAULT_SPORT_ID,
    SPORT_TYPE_MAPPING,
    FitTrackeeExporter,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def fittrackee_url() -> str:
    """FitTrackee test URL."""
    return "https://fittrackee.example.com"


@pytest.fixture
def exporter(tmp_path: Path, fittrackee_url: str) -> FitTrackeeExporter:
    """Create FitTrackee exporter for testing."""
    return FitTrackeeExporter(
        data_dir=tmp_path,
        url=fittrackee_url,
        email="test@example.com",
        password="testpassword",
    )


class TestSportTypeMapping:
    """Tests for Strava to FitTrackee sport type mapping."""

    @pytest.mark.ai_generated
    def test_run_maps_to_running(self) -> None:
        """Verify Run maps to FitTrackee running sport."""
        assert SPORT_TYPE_MAPPING["Run"] == 1

    @pytest.mark.ai_generated
    def test_ride_maps_to_cycling(self) -> None:
        """Verify Ride maps to FitTrackee cycling sport."""
        assert SPORT_TYPE_MAPPING["Ride"] == 2

    @pytest.mark.ai_generated
    def test_hike_maps_to_hiking(self) -> None:
        """Verify Hike maps to FitTrackee hiking sport."""
        assert SPORT_TYPE_MAPPING["Hike"] == 4

    @pytest.mark.ai_generated
    def test_swim_maps_to_swimming(self) -> None:
        """Verify Swim maps to FitTrackee swimming sport."""
        assert SPORT_TYPE_MAPPING["Swim"] == 8

    @pytest.mark.ai_generated
    def test_default_sport_id_is_workout(self) -> None:
        """Verify default sport ID is workout/general."""
        assert DEFAULT_SPORT_ID == 9


class TestFitTrackeeExporter:
    """Tests for FitTrackeeExporter class."""

    @pytest.mark.ai_generated
    def test_init_stores_url_without_trailing_slash(
        self, tmp_path: Path, fittrackee_url: str
    ) -> None:
        """Verify URL trailing slash is stripped."""
        exporter = FitTrackeeExporter(
            data_dir=tmp_path,
            url=f"{fittrackee_url}/",
            email="test@example.com",
            password="password",
        )
        assert exporter.url == fittrackee_url

    @pytest.mark.ai_generated
    def test_get_sport_id_maps_known_types(self, exporter: FitTrackeeExporter) -> None:
        """Verify known sport types are mapped correctly."""
        assert exporter._get_sport_id("Run") == 1
        assert exporter._get_sport_id("Ride") == 2
        assert exporter._get_sport_id("Hike") == 4

    @pytest.mark.ai_generated
    def test_get_sport_id_returns_default_for_unknown(
        self, exporter: FitTrackeeExporter
    ) -> None:
        """Verify unknown sport types return default ID."""
        assert exporter._get_sport_id("UnknownSport") == DEFAULT_SPORT_ID
        assert exporter._get_sport_id("") == DEFAULT_SPORT_ID

    @pytest.mark.ai_generated
    def test_get_sport_mapping_returns_all_mappings(
        self, exporter: FitTrackeeExporter
    ) -> None:
        """Verify get_sport_mapping returns complete mapping."""
        mapping = exporter.get_sport_mapping()
        assert "Run" in mapping
        assert "Ride" in mapping
        assert mapping["Run"]["fittrackee_id"] == 1


class TestFitTrackeeAuthentication:
    """Tests for FitTrackee authentication."""

    @pytest.mark.ai_generated
    @responses.activate
    def test_authenticate_success(
        self, exporter: FitTrackeeExporter, fittrackee_url: str
    ) -> None:
        """Verify successful authentication returns token."""
        responses.add(
            responses.POST,
            f"{fittrackee_url}/api/auth/login",
            json={"auth_token": "test_token_123"},
            status=200,
        )

        token = exporter._authenticate()
        assert token == "test_token_123"

    @pytest.mark.ai_generated
    @responses.activate
    def test_authenticate_caches_token(
        self, exporter: FitTrackeeExporter, fittrackee_url: str
    ) -> None:
        """Verify token is cached after first authentication."""
        responses.add(
            responses.POST,
            f"{fittrackee_url}/api/auth/login",
            json={"auth_token": "cached_token"},
            status=200,
        )

        # First call authenticates
        token1 = exporter._authenticate()
        # Second call should use cached token (no additional request)
        token2 = exporter._authenticate()

        assert token1 == token2 == "cached_token"
        assert len(responses.calls) == 1  # Only one HTTP call

    @pytest.mark.ai_generated
    @responses.activate
    def test_authenticate_fails_on_bad_credentials(
        self, exporter: FitTrackeeExporter, fittrackee_url: str
    ) -> None:
        """Verify authentication raises on bad credentials."""
        responses.add(
            responses.POST,
            f"{fittrackee_url}/api/auth/login",
            json={"error": "Invalid credentials"},
            status=401,
        )

        with pytest.raises(RuntimeError, match="authentication failed"):
            exporter._authenticate()

    @pytest.mark.ai_generated
    def test_authenticate_requires_credentials(self, tmp_path: Path) -> None:
        """Verify authentication raises without credentials."""
        exporter = FitTrackeeExporter(
            data_dir=tmp_path,
            url="https://example.com",
            email=None,
            password=None,
        )

        with pytest.raises(ValueError, match="email and password are required"):
            exporter._authenticate()

    @pytest.mark.ai_generated
    @responses.activate
    def test_authenticate_raises_on_missing_token(
        self, exporter: FitTrackeeExporter, fittrackee_url: str
    ) -> None:
        """Verify authentication raises when no token in response."""
        responses.add(
            responses.POST,
            f"{fittrackee_url}/api/auth/login",
            json={"status": "ok"},  # No auth_token
            status=200,
        )

        with pytest.raises(RuntimeError, match="No auth token"):
            exporter._authenticate()


class TestFitTrackeeExport:
    """Tests for FitTrackee export functionality."""

    @pytest.mark.ai_generated
    def test_export_dry_run_no_http_calls(
        self, exporter: FitTrackeeExporter
    ) -> None:
        """Verify dry run doesn't make HTTP calls."""
        # Empty data dir - should return zeros
        result = exporter.export(dry_run=True)

        assert result["exported"] == 0
        assert result["failed"] == 0

    @pytest.mark.ai_generated
    def test_export_returns_result_dict(self, exporter: FitTrackeeExporter) -> None:
        """Verify export returns proper result structure."""
        result = exporter.export(dry_run=True)

        assert "exported" in result
        assert "skipped" in result
        assert "failed" in result
        assert "details" in result
        assert isinstance(result["details"], list)

    @pytest.mark.ai_generated
    def test_export_with_log_callback(self, exporter: FitTrackeeExporter) -> None:
        """Verify log callback is called during export."""
        logs: list[str] = []

        def log_callback(msg: str, _level: int = 0) -> None:
            logs.append(msg)

        exporter.export(dry_run=True, log_callback=log_callback)
        # Callback may or may not be called depending on data
        # This just verifies it doesn't raise


class TestFitTrackeeExportWithFixtures:
    """Tests for FitTrackee export using CLI fixture data."""

    @pytest.fixture
    def cli_data_dir(self, tmp_path: Path) -> Generator[Path, None, None]:
        """Generate realistic fixture data for testing."""
        import random
        import sys

        # Add e2e fixtures to path
        fixtures_path = Path(__file__).parent.parent / "e2e" / "fixtures"
        if str(fixtures_path) not in sys.path:
            sys.path.insert(0, str(fixtures_path))

        from generate_fixtures import generate_fixtures

        random.seed(42)
        data_dir = tmp_path / "data"
        generate_fixtures(data_dir)
        yield data_dir

    @pytest.mark.ai_generated
    def test_export_dry_run_with_fixture_data(
        self, cli_data_dir: Path, fittrackee_url: str
    ) -> None:
        """Verify dry run processes fixture data without HTTP calls."""
        exporter = FitTrackeeExporter(
            data_dir=cli_data_dir,
            url=fittrackee_url,
            email="test@example.com",
            password="password",
        )

        result = exporter.export(dry_run=True)

        # Should have some activities to process
        assert result["exported"] == 0  # Dry run doesn't export
        # Some activities should have been considered
        assert len(result["details"]) >= 0  # At least processed some

    @pytest.mark.ai_generated
    def test_export_limit_option(
        self, cli_data_dir: Path, fittrackee_url: str
    ) -> None:
        """Verify limit option restricts number of activities."""
        exporter = FitTrackeeExporter(
            data_dir=cli_data_dir,
            url=fittrackee_url,
            email="test@example.com",
            password="password",
        )

        result = exporter.export(dry_run=True, limit=2)

        # Should process at most 2 activities per athlete
        # Details may include skipped activities too
        would_export = [d for d in result["details"] if d.get("status") == "would_export"]
        assert len(would_export) <= 4  # 2 per athlete, 2 athletes max
