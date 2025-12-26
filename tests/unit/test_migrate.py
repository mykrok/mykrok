"""Tests for migrate module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mykrok.lib.paths import ATHLETE_PREFIX
from mykrok.services.migrate import (
    LOG_GITATTRIBUTES_RULE,
    add_log_gitattributes_rule,
    migrate_center_to_start_coords,
    migrate_config_directory,
    run_full_migration,
    update_dataset_template_files,
    update_gitattributes_paths,
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
class TestMigrateConfigDirectory:
    """Tests for migrate_config_directory function."""

    def test_renames_strava_backup_to_mykrok(self, tmp_path: Path) -> None:
        """Test renaming .strava-backup directory to .mykrok."""
        # Create legacy config directory
        old_dir = tmp_path / ".strava-backup"
        old_dir.mkdir()
        config_file = old_dir / "config.toml"
        config_file.write_text('[strava]\nclient_id = "test"\n')

        result = migrate_config_directory(tmp_path)

        assert result["dir_renamed"] is not None
        assert ".strava-backup" in result["dir_renamed"][0]
        assert ".mykrok" in result["dir_renamed"][1]
        assert not old_dir.exists()
        new_dir = tmp_path / ".mykrok"
        assert new_dir.exists()
        assert (new_dir / "config.toml").exists()
        assert (new_dir / "config.toml").read_text() == '[strava]\nclient_id = "test"\n'

    def test_migrates_legacy_single_file_config(self, tmp_path: Path) -> None:
        """Test migrating .strava-backup.toml to .mykrok/config.toml."""
        # Create legacy single-file config
        legacy_file = tmp_path / ".strava-backup.toml"
        legacy_file.write_text('[strava]\nclient_id = "legacy"\n')

        result = migrate_config_directory(tmp_path)

        assert result["file_migrated"] is not None
        assert ".strava-backup.toml" in result["file_migrated"][0]
        assert ".mykrok/config.toml" in result["file_migrated"][1]
        assert not legacy_file.exists()
        new_config = tmp_path / ".mykrok" / "config.toml"
        assert new_config.exists()
        assert new_config.read_text() == '[strava]\nclient_id = "legacy"\n'

    def test_skips_if_mykrok_already_exists(self, tmp_path: Path) -> None:
        """Test skipping migration if .mykrok already exists."""
        # Create both directories
        old_dir = tmp_path / ".strava-backup"
        old_dir.mkdir()
        (old_dir / "config.toml").write_text('[strava]\nclient_id = "old"\n')

        new_dir = tmp_path / ".mykrok"
        new_dir.mkdir()
        (new_dir / "config.toml").write_text('[strava]\nclient_id = "new"\n')

        result = migrate_config_directory(tmp_path)

        assert result["dir_renamed"] is None
        # Both directories should still exist
        assert old_dir.exists()
        assert new_dir.exists()
        # New config should be unchanged
        assert (new_dir / "config.toml").read_text() == '[strava]\nclient_id = "new"\n'

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        """Test dry run mode doesn't rename directory."""
        old_dir = tmp_path / ".strava-backup"
        old_dir.mkdir()
        (old_dir / "config.toml").write_text('[strava]\nclient_id = "test"\n')

        result = migrate_config_directory(tmp_path, dry_run=True)

        assert result["dir_renamed"] is not None
        # Directory should still exist with old name
        assert old_dir.exists()
        assert not (tmp_path / ".mykrok").exists()

    def test_handles_no_legacy_config(self, tmp_path: Path) -> None:
        """Test handling when no legacy config exists."""
        result = migrate_config_directory(tmp_path)

        assert result["dir_renamed"] is None
        assert result["file_migrated"] is None


@pytest.mark.ai_generated
class TestUpdateGitattributesPaths:
    """Tests for update_gitattributes_paths function."""

    def test_updates_legacy_paths(self, tmp_path: Path) -> None:
        """Test updating .strava-backup paths to .mykrok in .gitattributes."""
        gitattributes = tmp_path / ".gitattributes"
        gitattributes.write_text(
            "# Config file\n"
            ".strava-backup/config.toml annex.largefiles=anything\n"
            "*.log annex.largefiles=anything\n"
        )

        result = update_gitattributes_paths(tmp_path)

        assert result is True
        content = gitattributes.read_text()
        assert ".mykrok/config.toml" in content
        assert ".strava-backup/config.toml" not in content
        assert "*.log annex.largefiles=anything" in content

    def test_skips_if_no_legacy_paths(self, tmp_path: Path) -> None:
        """Test skipping if no legacy paths exist."""
        gitattributes = tmp_path / ".gitattributes"
        original_content = ".mykrok/config.toml annex.largefiles=anything\n"
        gitattributes.write_text(original_content)

        result = update_gitattributes_paths(tmp_path)

        assert result is False
        assert gitattributes.read_text() == original_content

    def test_returns_false_if_file_missing(self, tmp_path: Path) -> None:
        """Test returning False when .gitattributes doesn't exist."""
        result = update_gitattributes_paths(tmp_path)
        assert result is False

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        """Test dry run mode doesn't modify file."""
        gitattributes = tmp_path / ".gitattributes"
        original_content = ".strava-backup/config.toml annex.largefiles=anything\n"
        gitattributes.write_text(original_content)

        result = update_gitattributes_paths(tmp_path, dry_run=True)

        assert result is True
        assert gitattributes.read_text() == original_content


@pytest.mark.ai_generated
class TestUpdateDatasetTemplateFiles:
    """Tests for update_dataset_template_files function."""

    def test_updates_readme_references(self, tmp_path: Path) -> None:
        """Test updating strava-backup references in README.md."""
        readme = tmp_path / "README.md"
        readme.write_text(
            "# Strava Backup Dataset\n\n"
            "Edit `.strava-backup/config.toml` and run `strava-backup auth`.\n"
        )

        result = update_dataset_template_files(tmp_path)

        assert "README.md" in result
        content = readme.read_text()
        assert "MyKrok" in content
        assert ".mykrok/config.toml" in content
        assert "mykrok auth" in content
        assert ".strava-backup" not in content
        assert "strava-backup" not in content

    def test_updates_makefile_references(self, tmp_path: Path) -> None:
        """Test updating strava-backup references in Makefile."""
        makefile = tmp_path / "Makefile"
        makefile.write_text(
            "# Strava Backup Makefile\n"
            "sync:\n"
            '\tdatalad run -m "Sync new Strava activities" "strava-backup sync"\n'
        )

        result = update_dataset_template_files(tmp_path)

        assert "Makefile" in result
        content = makefile.read_text()
        assert "MyKrok" in content
        assert "mykrok sync" in content
        assert '"Sync new activities"' in content
        assert "strava-backup" not in content

    def test_updates_gitignore_references(self, tmp_path: Path) -> None:
        """Test updating strava-backup references in .gitignore."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(
            "# Strava Backup\n"
            "# Note: .strava-backup/config.toml is tracked\n"
        )

        result = update_dataset_template_files(tmp_path)

        assert ".gitignore" in result
        content = gitignore.read_text()
        assert "MyKrok" in content
        assert ".mykrok/config.toml" in content
        assert ".strava-backup" not in content

    def test_skips_if_no_legacy_references(self, tmp_path: Path) -> None:
        """Test skipping files without legacy references."""
        readme = tmp_path / "README.md"
        original = "# MyKrok Dataset\n\nAlready updated.\n"
        readme.write_text(original)

        result = update_dataset_template_files(tmp_path)

        assert result == []
        assert readme.read_text() == original

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        """Test dry run mode doesn't modify files."""
        readme = tmp_path / "README.md"
        original = "# Strava Backup Dataset\n"
        readme.write_text(original)

        result = update_dataset_template_files(tmp_path, dry_run=True)

        assert "README.md" in result
        assert readme.read_text() == original


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

        original_content = "datetime\tname\tdistance_m\n" "20251218T120000\tTest Run\t5000\n"
        sessions_tsv = athlete_dir / "sessions.tsv"
        sessions_tsv.write_text(original_content)

        result = migrate_center_to_start_coords(tmp_path)

        assert result == 0
        assert sessions_tsv.read_text() == original_content

    def test_handles_empty_directory(self, tmp_path: Path) -> None:
        """Test handling empty data directory."""
        result = migrate_center_to_start_coords(tmp_path)
        assert result == 0


def create_legacy_datalad_dataset(dataset_dir: Path) -> dict[str, Path]:
    """Create a fake DataLad dataset with old strava-backup naming.

    Simulates a dataset created before the rename to mykrok, with:
    - .strava-backup/ config directory
    - Old README.md with "Strava Backup" references
    - Old Makefile with "Strava" references
    - Old .gitignore with "Strava Backup" comment
    - Old .gitattributes with .strava-backup/config.toml

    Returns:
        Dictionary with paths to created files.
    """
    # Create .strava-backup config directory (old naming)
    config_dir = dataset_dir / ".strava-backup"
    config_dir.mkdir(parents=True)

    config_file = config_dir / "config.toml"
    config_file.write_text(
        '[strava]\nclient_id = "12345"\nclient_secret = "secret"\n\n'
        '[data]\ndirectory = ".."\n'
    )

    # Create old README.md
    readme_file = dataset_dir / "README.md"
    readme_file.write_text(
        "# Strava Backup Dataset\n\n"
        "This is a DataLad dataset for backing up Strava activities.\n\n"
        "## Setup\n\n"
        "1. Edit `.strava-backup/config.toml` with your credentials\n"
        "2. Run `strava-backup auth`\n"
    )

    # Create old Makefile
    makefile = dataset_dir / "Makefile"
    makefile.write_text(
        "# Strava Backup Makefile\n"
        "# ======================\n\n"
        "sync:\n"
        '\tdatalad run -m "Sync new Strava activities" \\\n'
        '\t\t-o "athl=*" \\\n'
        '\t\t"strava-backup sync"\n\n'
        "sync-full:\n"
        '\tdatalad run -m "Full Strava sync" \\\n'
        '\t\t-o "athl=*" \\\n'
        '\t\t"strava-backup sync --full"\n\n'
        "help:\n"
        '\t@echo "Strava Backup Commands:"\n'
    )

    # Create old .gitignore
    gitignore = dataset_dir / ".gitignore"
    gitignore.write_text(
        "# Strava Backup\n"
        "# Note: .strava-backup/config.toml is tracked by git-annex\n"
        "*.pyc\n"
        "__pycache__/\n"
    )

    # Create old .gitattributes
    gitattributes = dataset_dir / ".gitattributes"
    gitattributes.write_text(
        "# Force .strava-backup/config.toml to be tracked by git-annex\n"
        ".strava-backup/config.toml annex.largefiles=anything\n"
        "*.log annex.largefiles=anything\n"
    )

    return {
        "config_dir": config_dir,
        "config_file": config_file,
        "readme_file": readme_file,
        "makefile": makefile,
        "gitignore": gitignore,
        "gitattributes": gitattributes,
    }


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
    info_json.write_text(
        json.dumps(
            {
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
            }
        )
    )

    # Create tracking.json manifest (no actual parquet, but manifest exists)
    tracking_json = session_dir / "tracking.json"
    tracking_json.write_text(
        json.dumps(
            {
                "columns": ["time", "lat", "lng", "altitude"],
                "row_count": 100,
                "has_gps": True,
                "has_hr": False,
                "has_power": False,
            }
        )
    )

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

    def test_migrates_config_directory_in_full_migration(self, tmp_path: Path) -> None:
        """Test that full migration includes config directory rename."""
        # Create legacy config directory
        old_dir = tmp_path / ".strava-backup"
        old_dir.mkdir()
        (old_dir / "config.toml").write_text('[strava]\nclient_id = "test"\n')

        # Create legacy gitattributes
        gitattributes = tmp_path / ".gitattributes"
        gitattributes.write_text(".strava-backup/config.toml annex.largefiles=anything\n")

        # Create fake dataset to satisfy other migration requirements
        create_fake_legacy_dataset(tmp_path)

        results = run_full_migration(tmp_path)

        # Check config directory was migrated
        assert results["config_dir_migrated"] is not None
        assert not old_dir.exists()
        new_dir = tmp_path / ".mykrok"
        assert new_dir.exists()
        assert (new_dir / "config.toml").exists()

        # Check gitattributes was updated
        assert results["gitattributes_paths_updated"] is True
        content = gitattributes.read_text()
        assert ".mykrok/config.toml" in content
        assert ".strava-backup/config.toml" not in content

    def test_full_migration_removes_all_strava_backup_references(
        self, tmp_path: Path
    ) -> None:
        """Test that migration removes all strava-backup references from dataset files.

        This test creates a complete legacy dataset with old naming and verifies
        that after migration, no strava-backup references remain in:
        - .gitattributes
        - .gitignore
        - README.md
        - Makefile
        """
        # Create complete legacy dataset
        legacy_files = create_legacy_datalad_dataset(tmp_path)

        # Verify old references exist before migration
        assert ".strava-backup" in legacy_files["gitattributes"].read_text()
        assert "strava-backup" in legacy_files["readme_file"].read_text().lower()
        assert "strava-backup" in legacy_files["makefile"].read_text()
        assert ".strava-backup" in legacy_files["gitignore"].read_text()

        # Run migration
        results = run_full_migration(tmp_path)

        # Verify config directory was renamed
        assert results["config_dir_migrated"] is not None
        assert not legacy_files["config_dir"].exists()
        assert (tmp_path / ".mykrok").exists()

        # Check NO strava-backup references remain in any file
        files_to_check = [
            (".gitattributes", tmp_path / ".gitattributes"),
            (".gitignore", tmp_path / ".gitignore"),
            ("README.md", tmp_path / "README.md"),
            ("Makefile", tmp_path / "Makefile"),
        ]

        remaining_references = []
        for name, path in files_to_check:
            if path.exists():
                content = path.read_text()
                # Check for various forms of the old name
                if ".strava-backup" in content:
                    remaining_references.append(f"{name}: contains '.strava-backup'")
                if "strava-backup" in content and ".strava-backup" not in content:
                    # CLI command reference like "strava-backup sync"
                    remaining_references.append(f"{name}: contains 'strava-backup' command")

        assert not remaining_references, (
            "Legacy references remain after migration:\n"
            + "\n".join(f"  - {ref}" for ref in remaining_references)
        )

    def test_migration_finds_config_from_cwd_when_data_dir_is_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test migration works when data_dir is the PARENT of the dataset root.

        This simulates the real-world scenario where:
        - User is in /home/user/strava-mine/ (cwd = dataset root)
        - Config at .strava-backup/config.toml has directory = ".."
        - So data_dir resolves to /home/user/ (parent of dataset root)
        - Migration should still find .strava-backup/ in cwd
        """
        # Create dataset structure at tmp_path (simulates strava-mine/)
        dataset_root = tmp_path / "strava-mine"
        dataset_root.mkdir()

        # Create legacy config directory in dataset root
        old_config_dir = dataset_root / ".strava-backup"
        old_config_dir.mkdir()
        (old_config_dir / "config.toml").write_text(
            '[strava]\nclient_id = "test"\n\n[data]\ndirectory = ".."\n'
        )

        # Change cwd to dataset root (where user runs command from)
        monkeypatch.chdir(dataset_root)

        # data_dir is the PARENT (tmp_path), simulating resolved directory = ".."
        # This is the bug scenario - data_dir doesn't contain .strava-backup/
        data_dir = tmp_path  # Parent of dataset_root

        # Run migration with data_dir pointing to parent
        results = run_full_migration(data_dir)

        # Migration should find .strava-backup/ in cwd (dataset_root) and rename it
        assert results["config_dir_migrated"] is not None
        assert not old_config_dir.exists()
        assert (dataset_root / ".mykrok").exists()
        assert (dataset_root / ".mykrok" / "config.toml").exists()
