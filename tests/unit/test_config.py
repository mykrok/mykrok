"""Unit tests for configuration management."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from strava_backup.config import Config, load_config


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
