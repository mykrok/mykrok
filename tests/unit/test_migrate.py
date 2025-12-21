"""Tests for migrate module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from strava_backup.lib.paths import ATHLETE_PREFIX
from strava_backup.services.migrate import (
    LOG_GITATTRIBUTES_RULE,
    add_log_gitattributes_rule,
    migrate_center_to_start_coords,
    run_full_migration,
)


@pytest.mark.ai_generated
class TestAddLogGitattributesRule:
    """Tests for add_log_gitattributes_rule function."""

    def test_adds_rule_to_new_file(self, tmp_path: Path) -> None:
        """Test adding rule when .gitattributes doesn't exist."""
        result = add_log_gitattributes_rule(tmp_path)

        assert result is True
        gitattributes = tmp_path / ".gitattributes"
        assert gitattributes.exists()
        content = gitattributes.read_text()
        assert "*.log annex.largefiles=anything" in content

    def test_adds_rule_to_existing_file(self, tmp_path: Path) -> None:
        """Test adding rule to existing .gitattributes."""
        gitattributes = tmp_path / ".gitattributes"
        gitattributes.write_text("*.jpg annex.largefiles=anything\n")

        result = add_log_gitattributes_rule(tmp_path)

        assert result is True
        content = gitattributes.read_text()
        assert "*.jpg annex.largefiles=anything" in content
        assert "*.log annex.largefiles=anything" in content

    def test_skips_if_rule_already_present(self, tmp_path: Path) -> None:
        """Test skipping if rule already exists."""
        gitattributes = tmp_path / ".gitattributes"
        gitattributes.write_text(LOG_GITATTRIBUTES_RULE)
        original_content = gitattributes.read_text()

        result = add_log_gitattributes_rule(tmp_path)

        assert result is False
        # Content should not be modified at all
        assert gitattributes.read_text() == original_content

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        """Test dry run mode doesn't create/modify files."""
        result = add_log_gitattributes_rule(tmp_path, dry_run=True)

        assert result is True
        gitattributes = tmp_path / ".gitattributes"
        assert not gitattributes.exists()

    def test_dry_run_existing_file_no_rule(self, tmp_path: Path) -> None:
        """Test dry run with existing file that needs the rule."""
        gitattributes = tmp_path / ".gitattributes"
        original_content = "*.jpg annex.largefiles=anything\n"
        gitattributes.write_text(original_content)

        result = add_log_gitattributes_rule(tmp_path, dry_run=True)

        assert result is True
        # Content should not be modified
        assert gitattributes.read_text() == original_content


@pytest.mark.ai_generated
class TestMigrateCenterToStartCoords:
    """Tests for migrate_center_to_start_coords function."""

    def test_migrates_center_columns_to_start(self, tmp_path: Path) -> None:
        """Test renaming center_lat/center_lng to start_lat/start_lng."""
        # Create athlete directory with sessions.tsv using old column names
        athlete_dir = tmp_path / f"{ATHLETE_PREFIX}testuser"
        athlete_dir.mkdir()

        sessions_tsv = athlete_dir / "sessions.tsv"
        sessions_tsv.write_text(
            "datetime\tname\tcenter_lat\tcenter_lng\n"
            "20251218T120000\tTest Run\t40.123456\t-74.654321\n"
        )

        result = migrate_center_to_start_coords(tmp_path)

        assert result == 1
        content = sessions_tsv.read_text()
        assert "start_lat\tstart_lng" in content
        assert "center_lat" not in content
        assert "center_lng" not in content
        assert "40.123456\t-74.654321" in content

    def test_skips_if_already_migrated(self, tmp_path: Path) -> None:
        """Test skipping if start_lat/start_lng already exist."""
        athlete_dir = tmp_path / f"{ATHLETE_PREFIX}testuser"
        athlete_dir.mkdir()

        original_content = (
            "datetime\tname\tstart_lat\tstart_lng\n"
            "20251218T120000\tTest Run\t40.123456\t-74.654321\n"
        )
        sessions_tsv = athlete_dir / "sessions.tsv"
        sessions_tsv.write_text(original_content)

        result = migrate_center_to_start_coords(tmp_path)

        assert result == 0
        assert sessions_tsv.read_text() == original_content

    def test_skips_if_no_center_columns(self, tmp_path: Path) -> None:
        """Test skipping if no center columns exist."""
        athlete_dir = tmp_path / f"{ATHLETE_PREFIX}testuser"
        athlete_dir.mkdir()

        original_content = (
            "datetime\tname\tdistance_m\n"
            "20251218T120000\tTest Run\t5000\n"
        )
        sessions_tsv = athlete_dir / "sessions.tsv"
        sessions_tsv.write_text(original_content)

        result = migrate_center_to_start_coords(tmp_path)

        assert result == 0
        assert sessions_tsv.read_text() == original_content

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test handling empty data directory."""
        result = migrate_center_to_start_coords(tmp_path)
        assert result == 0


def create_fake_legacy_dataset(data_dir: Path) -> dict[str, Path]:
    """Create a fake dataset in the legacy format for migration testing.

    Creates a dataset structure as it would have existed before the
    center_lat/center_lng -> start_lat/start_lng migration.

    Returns:
        Dictionary with paths to created files.
    """
    # Create athlete directory
    athlete_dir = data_dir / f"{ATHLETE_PREFIX}testuser"
    athlete_dir.mkdir(parents=True)

    # Create a session directory with info.json
    session_dir = athlete_dir / "ses=20251218T120000"
    session_dir.mkdir()

    info_json = session_dir / "info.json"
    info_json.write_text(json.dumps({
        "id": 12345678,
        "name": "Morning Run",
        "type": "Run",
        "sport_type": "Run",
        "start_date": "2025-12-18T12:00:00Z",
        "start_date_local": "2025-12-18T07:00:00",
        "timezone": "(GMT-05:00) America/New_York",
        "distance": 5000.0,
        "moving_time": 1800,
        "elapsed_time": 1900,
        "total_elevation_gain": 50.0,
        "calories": 400,
        "has_gps": True,
        "has_photos": False,
        "photo_count": 0,
        "kudos_count": 5,
        "comment_count": 2,
        "athlete_count": 1,
        "comments": [],
        "kudos": [],
    }))

    # Create tracking.json manifest (no actual parquet, but manifest exists)
    tracking_json = session_dir / "tracking.json"
    tracking_json.write_text(json.dumps({
        "columns": ["time", "lat", "lng", "altitude"],
        "row_count": 100,
        "has_gps": True,
        "has_hr": False,
        "has_power": False,
    }))

    # Create sessions.tsv with OLD center_lat/center_lng columns
    sessions_tsv = athlete_dir / "sessions.tsv"
    sessions_tsv.write_text(
        "datetime\ttype\tsport\tname\tdistance_m\tmoving_time_s\t"
        "elapsed_time_s\televation_gain_m\tcalories\tavg_hr\tmax_hr\t"
        "avg_watts\tgear_id\tathletes\tkudos_count\tcomment_count\t"
        "has_gps\tphotos_path\tphoto_count\tcenter_lat\tcenter_lng\n"
        "20251218T120000\tRun\tRun\tMorning Run\t5000.0\t1800\t1900\t50.0\t"
        "400\t\t\t\t\t1\t5\t2\ttrue\t\t0\t40.748817\t-73.985428\n"
    )

    return {
        "athlete_dir": athlete_dir,
        "session_dir": session_dir,
        "info_json": info_json,
        "tracking_json": tracking_json,
        "sessions_tsv": sessions_tsv,
    }


@pytest.mark.ai_generated
class TestRunFullMigration:
    """Tests for run_full_migration function."""

    def test_migrates_legacy_dataset(self, tmp_path: Path) -> None:
        """Test full migration of a legacy dataset with center_lat/center_lng."""
        # Create fake legacy dataset
        paths = create_fake_legacy_dataset(tmp_path)

        # Run migration
        results = run_full_migration(tmp_path)

        # Check results
        assert results["coords_columns_migrated"] == 1
        assert results["athletes_tsv"] is not None

        # Verify sessions.tsv was migrated
        content = paths["sessions_tsv"].read_text()
        assert "start_lat\tstart_lng" in content
        assert "center_lat" not in content
        assert "center_lng" not in content
        # Values should be preserved
        assert "40.748817" in content
        assert "-73.985428" in content

        # Verify athletes.tsv was generated
        athletes_tsv = tmp_path / "athletes.tsv"
        assert athletes_tsv.exists()
        athletes_content = athletes_tsv.read_text()
        assert "testuser" in athletes_content

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        """Test that dry run doesn't modify files."""
        paths = create_fake_legacy_dataset(tmp_path)
        original_content = paths["sessions_tsv"].read_text()

        results = run_full_migration(tmp_path, dry_run=True)

        # sessions.tsv should not be modified
        assert paths["sessions_tsv"].read_text() == original_content
        # athletes.tsv should not be created
        athletes_tsv = tmp_path / "athletes.tsv"
        assert not athletes_tsv.exists()
        # coords_columns_migrated should be 0 in dry run
        assert results["coords_columns_migrated"] == 0

    def test_idempotent_migration(self, tmp_path: Path) -> None:
        """Test that running migration twice doesn't break anything."""
        create_fake_legacy_dataset(tmp_path)

        # First migration
        results1 = run_full_migration(tmp_path)
        assert results1["coords_columns_migrated"] == 1

        # Second migration should be a no-op for column rename
        results2 = run_full_migration(tmp_path)
        assert results2["coords_columns_migrated"] == 0

    def test_handles_empty_data_directory(self, tmp_path: Path) -> None:
        """Test migration on empty data directory."""
        results = run_full_migration(tmp_path)

        assert results["coords_columns_migrated"] == 0
        assert results["prefix_renames"] == []
