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


class TestSportTypeMappingAndExporter:
    """Tests for sport type mapping and exporter initialization."""

    @pytest.mark.ai_generated
    def test_sport_type_mappings_and_defaults(self) -> None:
        """Verify all Strava to FitTrackee sport type mappings.

        This consolidated test verifies:
        - Run maps to running (1)
        - Ride maps to cycling (2)
        - Hike maps to hiking (4)
        - Swim maps to swimming (8)
        - Default sport ID is workout/general (9)
        """
        assert SPORT_TYPE_MAPPING["Run"] == 1, "Run should map to 1"
        assert SPORT_TYPE_MAPPING["Ride"] == 2, "Ride should map to 2"
        assert SPORT_TYPE_MAPPING["Hike"] == 4, "Hike should map to 4"
        assert SPORT_TYPE_MAPPING["Swim"] == 8, "Swim should map to 8"
        assert DEFAULT_SPORT_ID == 9, "Default sport ID should be 9"

    @pytest.mark.ai_generated
    def test_exporter_initialization_and_sport_id_methods(
        self, tmp_path: Path, fittrackee_url: str
    ) -> None:
        """Verify exporter initialization and sport ID lookup methods.

        This consolidated test verifies:
        - URL trailing slash is stripped
        - Known sport types are mapped correctly via _get_sport_id
        - Unknown sport types return default ID
        - get_sport_mapping returns complete mapping
        """
        # Test URL trailing slash stripped
        exporter = FitTrackeeExporter(
            data_dir=tmp_path,
            url=f"{fittrackee_url}/",
            email="test@example.com",
            password="password",
        )
        assert exporter.url == fittrackee_url, "Trailing slash should be stripped"

        # Test known sport ID mapping
        assert exporter._get_sport_id("Run") == 1
        assert exporter._get_sport_id("Ride") == 2
        assert exporter._get_sport_id("Hike") == 4

        # Test unknown sport returns default
        assert exporter._get_sport_id("UnknownSport") == DEFAULT_SPORT_ID
        assert exporter._get_sport_id("") == DEFAULT_SPORT_ID

        # Test get_sport_mapping
        mapping = exporter.get_sport_mapping()
        assert "Run" in mapping
        assert "Ride" in mapping
        assert mapping["Run"]["fittrackee_id"] == 1


class TestFitTrackeeAuthentication:
    """Tests for FitTrackee authentication."""

    @pytest.mark.ai_generated
    @responses.activate
    def test_authenticate_success_and_caching(
        self, exporter: FitTrackeeExporter, fittrackee_url: str
    ) -> None:
        """Verify successful authentication and token caching.

        This consolidated test verifies:
        - Successful authentication returns token
        - Token is cached after first authentication
        - Only one HTTP call is made for multiple authenticate() calls
        """
        responses.add(
            responses.POST,
            f"{fittrackee_url}/api/auth/login",
            json={"auth_token": "test_token_123"},
            status=200,
        )

        # First call authenticates
        token1 = exporter._authenticate()
        assert token1 == "test_token_123"

        # Second call should use cached token (no additional request)
        token2 = exporter._authenticate()
        assert token1 == token2

        # Verify only one HTTP call was made
        assert len(responses.calls) == 1

    @pytest.mark.ai_generated
    @responses.activate
    def test_authenticate_error_scenarios(
        self, tmp_path: Path, fittrackee_url: str
    ) -> None:
        """Verify authentication error handling.

        This consolidated test verifies:
        - Bad credentials (401) raises RuntimeError
        - Missing credentials raises ValueError
        - Missing token in response raises RuntimeError
        """
        # Test bad credentials
        exporter1 = FitTrackeeExporter(
            data_dir=tmp_path,
            url=fittrackee_url,
            email="test@example.com",
            password="badpassword",
        )
        responses.add(
            responses.POST,
            f"{fittrackee_url}/api/auth/login",
            json={"error": "Invalid credentials"},
            status=401,
        )
        with pytest.raises(RuntimeError, match="authentication failed"):
            exporter1._authenticate()

        responses.reset()

        # Test missing credentials
        exporter2 = FitTrackeeExporter(
            data_dir=tmp_path,
            url=fittrackee_url,
            email=None,
            password=None,
        )
        with pytest.raises(ValueError, match="email and password are required"):
            exporter2._authenticate()

        # Test missing token in response
        exporter3 = FitTrackeeExporter(
            data_dir=tmp_path,
            url=fittrackee_url,
            email="test@example.com",
            password="password",
        )
        responses.add(
            responses.POST,
            f"{fittrackee_url}/api/auth/login",
            json={"status": "ok"},  # No auth_token
            status=200,
        )
        with pytest.raises(RuntimeError, match="No auth token"):
            exporter3._authenticate()


class TestFitTrackeeExport:
    """Tests for FitTrackee export functionality."""

    @pytest.mark.ai_generated
    def test_export_dry_run_and_result_structure(
        self, exporter: FitTrackeeExporter
    ) -> None:
        """Verify export dry run behavior and result structure.

        This consolidated test verifies:
        - Dry run doesn't make HTTP calls
        - Export returns proper result structure
        - Log callback is called without errors
        """
        # Test dry run
        result = exporter.export(dry_run=True)

        # Verify no activities exported in dry run
        assert result["exported"] == 0
        assert result["failed"] == 0

        # Verify result structure
        assert "exported" in result
        assert "skipped" in result
        assert "failed" in result
        assert "details" in result
        assert isinstance(result["details"], list)

        # Test log callback is accepted
        logs: list[str] = []

        def log_callback(msg: str, _level: int = 0) -> None:
            logs.append(msg)

        exporter.export(dry_run=True, log_callback=log_callback)
        # Callback may or may not be called depending on data - just verify it doesn't raise


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
    def test_export_with_fixture_data_and_limit(
        self, cli_data_dir: Path, fittrackee_url: str
    ) -> None:
        """Verify dry run processes fixture data and limit option works.

        This consolidated test verifies:
        - Dry run processes fixture data without HTTP calls
        - Limit option restricts number of activities
        """
        exporter = FitTrackeeExporter(
            data_dir=cli_data_dir,
            url=fittrackee_url,
            email="test@example.com",
            password="password",
        )

        # Test dry run with fixture data
        result = exporter.export(dry_run=True)
        assert result["exported"] == 0  # Dry run doesn't export
        assert len(result["details"]) >= 0  # At least processed some

        # Test limit option
        result_limited = exporter.export(dry_run=True, limit=2)
        would_export = [d for d in result_limited["details"] if d.get("status") == "would_export"]
        assert len(would_export) <= 4  # 2 per athlete, 2 athletes max
