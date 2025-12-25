"""Unit tests for path utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mykrok.lib.paths import (
    format_session_datetime,
    get_athlete_dir,
    get_session_dir,
    parse_session_datetime,
)


@pytest.mark.ai_generated
class TestPathUtils:
    """Tests for path utility functions."""

    def test_format_session_datetime(self) -> None:
        """Test datetime formatting for session keys."""
        dt = datetime(2025, 12, 18, 6, 30, 0)
        result = format_session_datetime(dt)

        assert result == "20251218T063000"

    def test_parse_session_datetime(self) -> None:
        """Test parsing session keys back to datetime."""
        session_key = "20251218T063000"
        result = parse_session_datetime(session_key)

        assert result.year == 2025
        assert result.month == 12
        assert result.day == 18
        assert result.hour == 6
        assert result.minute == 30

    def test_get_athlete_dir(self, temp_data_dir: Path) -> None:
        """Test athlete directory path generation."""
        result = get_athlete_dir(temp_data_dir, "testuser")

        assert result == temp_data_dir / "athl=testuser"

    def test_get_session_dir(self, temp_data_dir: Path) -> None:
        """Test session directory path generation."""
        dt = datetime(2025, 12, 18, 6, 30, 0)
        result = get_session_dir(temp_data_dir, "testuser", dt)

        assert result == temp_data_dir / "athl=testuser" / "ses=20251218T063000"
