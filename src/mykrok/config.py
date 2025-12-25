"""Configuration management for MyKrok.

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


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "mykrok" / "config.toml"
LOCAL_CONFIG_DIR = Path(".mykrok")
LOCAL_CONFIG_PATH = LOCAL_CONFIG_DIR / "config.toml"
LOCAL_TOKENS_PATH = LOCAL_CONFIG_DIR / "oauth-tokens.toml"
# Legacy paths for backward compatibility (from when project was called strava-backup)
LEGACY_LOCAL_CONFIG_DIR = Path(".strava-backup")
LEGACY_LOCAL_CONFIG_PATH = LEGACY_LOCAL_CONFIG_DIR / "config.toml"
LEGACY_LOCAL_CONFIG_FILE = Path(".strava-backup.toml")
DEFAULT_DATA_DIR = Path(".")


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
    2. Explicit config_path argument
    3. Local .mykrok/config.toml in current directory
    4. Legacy .strava-backup/config.toml (backward compatibility)
    5. Legacy .strava-backup.toml in current directory (backward compatibility)
    6. Global ~/.config/mykrok/config.toml
    7. Default values

    OAuth tokens are loaded separately from .mykrok/oauth-tokens.toml
    if present, keeping sensitive tokens separate from config.

    Args:
        config_path: Path to configuration file. If None, searches default locations.

    Returns:
        Populated Config object.
    """
    config = Config()

    # Determine config path with precedence
    if config_path is None:
        # Check environment variable first (support both new and legacy names)
        env_config = _get_env_value("MYKROK_CONFIG") or _get_env_value("STRAVA_BACKUP_CONFIG")
        if env_config:
            config_path = Path(env_config)
        # Check new .mykrok/config.toml
        elif LOCAL_CONFIG_PATH.exists():
            config_path = LOCAL_CONFIG_PATH
        # Check legacy .strava-backup/config.toml for backward compatibility
        elif LEGACY_LOCAL_CONFIG_PATH.exists():
            config_path = LEGACY_LOCAL_CONFIG_PATH
        # Then check legacy .strava-backup.toml for backward compatibility
        elif LEGACY_LOCAL_CONFIG_FILE.exists():
            config_path = LEGACY_LOCAL_CONFIG_FILE
        # Finally fall back to global config
        else:
            config_path = DEFAULT_CONFIG_PATH

    config.config_path = config_path

    # Load from file if exists
    if config_path.exists():
        config = _load_from_file(config_path, config)

    # Load tokens from separate file if it exists
    # Tokens file is in the same directory as the config file
    if config_path.parent == LOCAL_CONFIG_DIR or config_path == LOCAL_CONFIG_PATH:
        tokens_path = LOCAL_TOKENS_PATH
    else:
        tokens_path = config_path.parent / "oauth-tokens.toml"

    if tokens_path.exists():
        config = _load_tokens_from_file(tokens_path, config)

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
        # Also load tokens from main config for backward compatibility
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


def _load_tokens_from_file(path: Path, config: Config) -> Config:
    """Load OAuth tokens from separate tokens file.

    Args:
        path: Path to tokens TOML file.
        config: Existing config to update.

    Returns:
        Updated Config object.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)

    # Tokens override any tokens in main config
    if "strava" in data:
        strava = data["strava"]
        if "access_token" in strava:
            config.strava.access_token = strava["access_token"]
        if "refresh_token" in strava:
            config.strava.refresh_token = strava["refresh_token"]
        if "token_expires_at" in strava:
            config.strava.token_expires_at = strava["token_expires_at"]

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

    # Data directory (support both new and legacy env var names)
    if data_dir := _get_env_value("MYKROK_DATA_DIR") or _get_env_value("STRAVA_BACKUP_DATA_DIR"):
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
    """Save OAuth tokens to a separate tokens file.

    Tokens are saved separately from the main config file so they can be
    gitignored while the main config remains version-controlled.

    Args:
        config: Current configuration.
        access_token: OAuth access token.
        refresh_token: OAuth refresh token.
        expires_at: Token expiration timestamp.
    """
    import tomlkit

    if config.config_path is None:
        config.config_path = DEFAULT_CONFIG_PATH

    # Determine tokens file path - same directory as config
    if config.config_path.parent == LOCAL_CONFIG_DIR or config.config_path == LOCAL_CONFIG_PATH:
        tokens_path = LOCAL_TOKENS_PATH
    else:
        tokens_path = config.config_path.parent / "oauth-tokens.toml"

    # Ensure directory exists
    tokens_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing tokens file or create new document
    if tokens_path.exists():
        with open(tokens_path, encoding="utf-8") as f:
            doc = tomlkit.load(f)
    else:
        doc = tomlkit.document()
        doc.add(tomlkit.comment("OAuth tokens for MyKrok"))
        doc.add(tomlkit.comment("This file is auto-generated and should be gitignored"))
        doc.add(tomlkit.nl())

    # Ensure strava section exists
    if "strava" not in doc:
        doc["strava"] = tomlkit.table()

    # Update token fields (type: ignore for tomlkit's imprecise stubs)
    doc["strava"]["access_token"] = access_token  # type: ignore[index]
    doc["strava"]["refresh_token"] = refresh_token  # type: ignore[index]
    doc["strava"]["token_expires_at"] = expires_at  # type: ignore[index]

    # Write tokens file
    with open(tokens_path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(doc))

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

    with open(path, "w", encoding="utf-8") as f:
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
