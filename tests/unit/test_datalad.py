"""Unit tests for DataLad dataset creation."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.ai_generated
class TestDataladDatasetCreation:
    """Tests for DataLad dataset creation."""

    def test_create_dataset_basic(self, tmp_path: Path) -> None:
        """Test basic dataset creation."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        result = create_datalad_dataset(dataset_path)

        # Check return value
        assert result["status"] == "created"
        assert result["path"] == str(dataset_path)

        # Check dataset was created
        assert dataset_path.exists()
        assert (dataset_path / ".git").exists()
        assert (dataset_path / ".datalad").exists()

    def test_create_dataset_files(self, tmp_path: Path) -> None:
        """Test that all template files are created."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        # Check config directory and files
        config_dir = dataset_path / ".mykrok"
        assert config_dir.exists()
        assert config_dir.is_dir()

        # Check config file
        config_file = config_dir / "config.toml"
        assert config_file.exists()
        config_content = config_file.read_text()
        assert "[strava]" in config_content
        assert "client_id" in config_content
        assert "client_secret" in config_content
        assert "[data]" in config_content
        assert "[sync]" in config_content

        # Check .gitignore for oauth-tokens.toml
        config_gitignore = config_dir / ".gitignore"
        assert config_gitignore.exists()
        assert "oauth-tokens.toml" in config_gitignore.read_text()

    def test_create_dataset_readme(self, tmp_path: Path) -> None:
        """Test that README.md is created with proper content."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        readme_file = dataset_path / "README.md"
        assert readme_file.exists()
        readme_content = readme_file.read_text()
        assert "Strava" in readme_content
        assert "DataLad" in readme_content
        assert "mykrok" in readme_content

    def test_create_dataset_makefile(self, tmp_path: Path) -> None:
        """Test that Makefile is created with datalad run targets."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        makefile = dataset_path / "Makefile"
        assert makefile.exists()
        makefile_content = makefile.read_text()
        assert "datalad run" in makefile_content
        assert "sync:" in makefile_content
        assert "mykrok sync" in makefile_content

    def test_create_dataset_no_data_subdir(self, tmp_path: Path) -> None:
        """Test that data is stored in root (no data/ subdirectory)."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        # Data should go directly in root, not in data/ subdirectory
        data_dir = dataset_path / "data"
        assert not data_dir.exists(), "data/ subdirectory should not be created"

        # Config should reference parent directory (.mykrok/config.toml -> ..)
        config_file = dataset_path / ".mykrok" / "config.toml"
        config_content = config_file.read_text()
        assert 'directory = ".."' in config_content

    def test_create_dataset_gitignore(self, tmp_path: Path) -> None:
        """Test that .gitignore is created/updated."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        gitignore = dataset_path / ".gitignore"
        assert gitignore.exists()

    def test_create_dataset_existing_empty_dir(self, tmp_path: Path) -> None:
        """Test creating dataset in existing empty directory."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "existing-empty"
        dataset_path.mkdir()

        result = create_datalad_dataset(dataset_path)
        assert result["status"] == "created"

    def test_create_dataset_existing_nonempty_fails(self, tmp_path: Path) -> None:
        """Test that creating dataset in non-empty directory fails."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "non-empty"
        dataset_path.mkdir()
        (dataset_path / "some-file.txt").write_text("content")

        with pytest.raises(FileExistsError):
            create_datalad_dataset(dataset_path)

    def test_create_dataset_force_overwrites(self, tmp_path: Path) -> None:
        """Test that force=True allows overwriting."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "force-test"
        dataset_path.mkdir()
        (dataset_path / "some-file.txt").write_text("content")

        result = create_datalad_dataset(dataset_path, force=True)
        assert result["status"] == "created"

    def test_create_dataset_config_has_comments(self, tmp_path: Path) -> None:
        """Test that config file has helpful comments."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        config_file = dataset_path / ".mykrok" / "config.toml"
        config_content = config_file.read_text()

        # Check for helpful comments
        assert "# " in config_content  # Has comments
        assert "strava.com/settings/api" in config_content  # Has URL reference
        assert "client_id" in config_content
        assert "client_secret" in config_content

    def test_create_dataset_makefile_has_help(self, tmp_path: Path) -> None:
        """Test that Makefile has help target."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        makefile = dataset_path / "Makefile"
        makefile_content = makefile.read_text()

        assert "help:" in makefile_content or ".PHONY:" in makefile_content

    def test_create_dataset_gitattributes(self, tmp_path: Path) -> None:
        """Test that .gitattributes is created with annex rules."""
        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        gitattributes = dataset_path / ".gitattributes"
        assert gitattributes.exists()
        content = gitattributes.read_text()
        # Should have rule to track config in git-annex
        assert ".mykrok/config.toml" in content
        assert "annex.largefiles" in content

    def test_create_dataset_config_is_annexed_unlocked(self, tmp_path: Path) -> None:
        """Test that config file is tracked by git-annex but unlocked (regular file)."""
        import subprocess

        from mykrok.services.datalad import create_datalad_dataset

        dataset_path = tmp_path / "test-dataset"
        create_datalad_dataset(dataset_path)

        config_file = dataset_path / ".mykrok" / "config.toml"
        assert config_file.exists()

        # Config should be a regular file (unlocked), not a symlink
        # This makes it easier to edit
        assert not config_file.is_symlink(), "Config file should be unlocked (not a symlink)"
        assert config_file.is_file(), "Config file should be a regular file"

        # Verify it's tracked by git-annex using whereis
        result = subprocess.run(
            ["git", "annex", "whereis", ".mykrok/config.toml"],
            cwd=str(dataset_path),
            capture_output=True,
            text=True,
        )
        # whereis should succeed (exit 0) if file is tracked by annex
        assert result.returncode == 0, "Config should be tracked by git-annex"
