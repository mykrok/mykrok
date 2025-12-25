"""Unit tests for configuration management."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from mykrok.config import Config, load_config


@pytest.mark.ai_generated
class TestConfig:
    """Tests for configuration management."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = Config()

        assert config.strava.client_id == ""
        assert config.sync.photos is True
        assert config.sync.streams is True
        assert config.sync.comments is True

    def test_load_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading configuration from environment variables."""
        monkeypatch.setenv("STRAVA_CLIENT_ID", "test_id")
        monkeypatch.setenv("STRAVA_CLIENT_SECRET", "test_secret")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config = load_config(config_path)

            assert config.strava.client_id == "test_id"
            assert config.strava.client_secret == "test_secret"

    def test_load_config_from_file(self) -> None:
        """Test loading configuration from TOML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
[strava]
client_id = "file_id"
client_secret = "file_secret"

[data]
directory = "/custom/path"

[sync]
photos = false
            """)

            config = load_config(config_path)

            assert config.strava.client_id == "file_id"
            assert config.sync.photos is False
            assert str(config.data.directory) == "/custom/path"

    def test_load_config_from_local_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Test loading configuration from local .mykrok/config.toml file."""
        # Create local config directory and file
        config_dir = tmp_path / ".mykrok"
        config_dir.mkdir()
        local_config = config_dir / "config.toml"
        local_config.write_text("""
[strava]
client_id = "local_id"
client_secret = "local_secret"
        """)

        # Change to temp directory and test
        monkeypatch.chdir(tmp_path)

        config = load_config()

        assert config.strava.client_id == "local_id"
        assert config.strava.client_secret == "local_secret"
        # Config path should be the local file
        assert config.config_path is not None
        assert config.config_path.name == "config.toml"
        assert config.config_path.parent.name == ".mykrok"

    def test_save_tokens_preserves_comments(self, tmp_path: Path) -> None:
        """Test that save_tokens saves to separate tokens file."""
        from mykrok.config import Config, StravaConfig, save_tokens

        # Create config directory with config file
        config_dir = tmp_path / ".mykrok"
        config_dir.mkdir()
        config_path = config_dir / "config.toml"
        config_path.write_text("""\
# This is an important comment
[strava]
# Client credentials from https://www.strava.com/settings/api
client_id = "my_id"
client_secret = "my_secret"  # Keep this secret!

[data]
# Where to store activity data
directory = ".."

[sync]
photos = true  # Download photos
""")

        # Create config object
        config = Config(
            strava=StravaConfig(client_id="my_id", client_secret="my_secret"),
            config_path=config_path,
        )

        # Save tokens
        save_tokens(config, "new_access_token", "new_refresh_token", 1234567890)

        # Check that original config file is unchanged
        config_content = config_path.read_text()
        assert "# This is an important comment" in config_content
        assert "# Client credentials from" in config_content
        assert "# Keep this secret!" in config_content
        assert "new_access_token" not in config_content  # Tokens are NOT in config

        # Check that tokens are saved to separate file
        tokens_path = config_dir / "oauth-tokens.toml"
        assert tokens_path.exists()
        tokens_content = tokens_path.read_text()
        assert "new_access_token" in tokens_content
        assert "new_refresh_token" in tokens_content
        assert "1234567890" in tokens_content
