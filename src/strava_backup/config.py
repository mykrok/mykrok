"""Configuration management for strava-backup.

Handles loading configuration from TOML files, environment variables,
and command-line options with proper precedence.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "strava-backup" / "config.toml"
DEFAULT_DATA_DIR = Path("./data")


@dataclass
class StravaConfig:
    """Strava API configuration."""

    client_id: str = ""
    client_secret: str = ""
    access_token: str = ""
    refresh_token: str = ""
    token_expires_at: int = 0
    exclude_athletes: list[str] = field(default_factory=list)


@dataclass
class DataConfig:
    """Data storage configuration."""

    directory: Path = field(default_factory=lambda: DEFAULT_DATA_DIR)


@dataclass
class FitTrackeeConfig:
    """FitTrackee export configuration."""

    url: str = ""
    email: str = ""
    password: str = ""


@dataclass
class SyncConfig:
    """Sync behavior configuration."""

    photos: bool = True
    streams: bool = True
    comments: bool = True


@dataclass
class Config:
    """Main configuration container."""

    strava: StravaConfig = field(default_factory=StravaConfig)
    data: DataConfig = field(default_factory=DataConfig)
    fittrackee: FitTrackeeConfig = field(default_factory=FitTrackeeConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    config_path: Path | None = None


def _get_env_value(key: str, default: str = "") -> str:
    """Get environment variable value."""
    return os.environ.get(key, default)


def _get_env_bool(key: str, default: bool = True) -> bool:
    """Get environment variable as boolean."""
    value = os.environ.get(key, "")
    if not value:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def load_config(config_path: Path | None = None) -> Config:
    """Load configuration from file and environment variables.

    Configuration is loaded with the following precedence (highest to lowest):
    1. Environment variables
    2. Configuration file
    3. Default values

    Args:
        config_path: Path to configuration file. If None, uses default location.

    Returns:
        Populated Config object.
    """
    config = Config()

    # Determine config path
    if config_path is None:
        env_config = _get_env_value("STRAVA_BACKUP_CONFIG")
        config_path = Path(env_config) if env_config else DEFAULT_CONFIG_PATH

    config.config_path = config_path

    # Load from file if exists
    if config_path.exists():
        config = _load_from_file(config_path, config)

    # Override with environment variables
    config = _apply_env_overrides(config)

    return config


def _load_from_file(path: Path, config: Config) -> Config:
    """Load configuration from TOML file.

    Args:
        path: Path to TOML file.
        config: Existing config to update.

    Returns:
        Updated Config object.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Strava section
    if "strava" in data:
        strava = data["strava"]
        config.strava.client_id = strava.get("client_id", config.strava.client_id)
        config.strava.client_secret = strava.get("client_secret", config.strava.client_secret)
        config.strava.access_token = strava.get("access_token", config.strava.access_token)
        config.strava.refresh_token = strava.get("refresh_token", config.strava.refresh_token)
        config.strava.token_expires_at = strava.get(
            "token_expires_at", config.strava.token_expires_at
        )
        if "exclude" in strava:
            config.strava.exclude_athletes = strava["exclude"].get(
                "athletes", config.strava.exclude_athletes
            )

    # Data section
    if "data" in data:
        data_section = data["data"]
        if "directory" in data_section:
            config.data.directory = Path(data_section["directory"])

    # FitTrackee section
    if "fittrackee" in data:
        ft = data["fittrackee"]
        config.fittrackee.url = ft.get("url", config.fittrackee.url)
        config.fittrackee.email = ft.get("email", config.fittrackee.email)
        config.fittrackee.password = ft.get("password", config.fittrackee.password)

    # Sync section
    if "sync" in data:
        sync = data["sync"]
        config.sync.photos = sync.get("photos", config.sync.photos)
        config.sync.streams = sync.get("streams", config.sync.streams)
        config.sync.comments = sync.get("comments", config.sync.comments)

    return config


def _apply_env_overrides(config: Config) -> Config:
    """Apply environment variable overrides to configuration.

    Args:
        config: Config to update.

    Returns:
        Updated Config object.
    """
    # Strava environment variables
    if client_id := _get_env_value("STRAVA_CLIENT_ID"):
        config.strava.client_id = client_id
    if client_secret := _get_env_value("STRAVA_CLIENT_SECRET"):
        config.strava.client_secret = client_secret

    # Data directory
    if data_dir := _get_env_value("STRAVA_BACKUP_DATA_DIR"):
        config.data.directory = Path(data_dir)

    # FitTrackee environment variables
    if ft_url := _get_env_value("FITTRACKEE_URL"):
        config.fittrackee.url = ft_url
    if ft_email := _get_env_value("FITTRACKEE_EMAIL"):
        config.fittrackee.email = ft_email
    if ft_password := _get_env_value("FITTRACKEE_PASSWORD"):
        config.fittrackee.password = ft_password

    return config


def save_tokens(config: Config, access_token: str, refresh_token: str, expires_at: int) -> None:
    """Save OAuth tokens to configuration file.

    Args:
        config: Current configuration.
        access_token: OAuth access token.
        refresh_token: OAuth refresh token.
        expires_at: Token expiration timestamp.
    """
    if config.config_path is None:
        config.config_path = DEFAULT_CONFIG_PATH

    # Ensure config directory exists
    config.config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or start fresh
    existing_data: dict[str, Any] = {}
    if config.config_path.exists():
        with open(config.config_path, "rb") as f:
            existing_data = tomllib.load(f)

    # Update strava section
    if "strava" not in existing_data:
        existing_data["strava"] = {}

    existing_data["strava"]["access_token"] = access_token
    existing_data["strava"]["refresh_token"] = refresh_token
    existing_data["strava"]["token_expires_at"] = expires_at

    # Write back as TOML
    _write_toml(config.config_path, existing_data)

    # Update in-memory config
    config.strava.access_token = access_token
    config.strava.refresh_token = refresh_token
    config.strava.token_expires_at = expires_at


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    """Write data to TOML file.

    Args:
        path: Path to write to.
        data: Data to write.
    """
    lines: list[str] = []

    for section, values in data.items():
        if isinstance(values, dict):
            lines.append(f"[{section}]")
            for key, value in values.items():
                if isinstance(value, dict):
                    # Handle nested sections like [strava.exclude]
                    lines.append(f"[{section}.{key}]")
                    for nested_key, nested_value in value.items():
                        lines.append(f"{nested_key} = {_format_toml_value(nested_value)}")
                else:
                    lines.append(f"{key} = {_format_toml_value(value)}")
            lines.append("")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def _format_toml_value(value: Any) -> str:
    """Format a Python value as TOML.

    Args:
        value: Value to format.

    Returns:
        TOML-formatted string.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, list):
        formatted = ", ".join(_format_toml_value(v) for v in value)
        return f"[{formatted}]"
    return str(value)


def ensure_data_dir(config: Config) -> Path:
    """Ensure data directory exists and return its path.

    Args:
        config: Configuration with data directory setting.

    Returns:
        Path to data directory.
    """
    data_dir = config.data.directory.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
