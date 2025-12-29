"""Tests for timezone history tracking and correction."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from mykrok.services.timezone import (
    TimezoneChange,
    TimezoneHistory,
    detect_timezone_from_coords,
    validate_timezone_history,
)


@pytest.fixture
def tmp_athlete_dir(tmp_path: Path) -> Path:
    """Create a temporary athlete directory."""
    athlete_dir = tmp_path / "athl=testuser"
    athlete_dir.mkdir(parents=True)
    return athlete_dir


class TestTimezoneChange:
    """Tests for TimezoneChange dataclass."""

    @pytest.mark.ai_generated
    def test_to_row(self) -> None:
        """Test conversion to TSV row."""
        change = TimezoneChange(
            datetime_utc=datetime(2024, 6, 15, 12, 0, 0),
            timezone="America/New_York",
            source="gps:ses=20240615T120000",
        )
        row = change.to_row()
        assert row["datetime_utc"] == "2024-06-15T12:00:00"
        assert row["timezone"] == "America/New_York"
        assert row["source"] == "gps:ses=20240615T120000"

    @pytest.mark.ai_generated
    def test_from_row(self) -> None:
        """Test creation from TSV row."""
        row = {
            "datetime_utc": "2024-06-15T12:00:00",
            "timezone": "America/Los_Angeles",
            "source": "manual",
        }
        change = TimezoneChange.from_row(row)
        assert change.datetime_utc == datetime(2024, 6, 15, 12, 0, 0)
        assert change.timezone == "America/Los_Angeles"
        assert change.source == "manual"

    @pytest.mark.ai_generated
    def test_from_row_with_z_suffix(self) -> None:
        """Test parsing datetime with Z suffix."""
        row = {
            "datetime_utc": "2024-06-15T12:00:00Z",
            "timezone": "UTC",
            "source": "test",
        }
        change = TimezoneChange.from_row(row)
        assert change.datetime_utc == datetime(2024, 6, 15, 12, 0, 0)
        assert change.datetime_utc.tzinfo is None  # Stored as naive


class TestTimezoneHistory:
    """Tests for TimezoneHistory class."""

    @pytest.mark.ai_generated
    def test_empty_history_uses_default(self, tmp_athlete_dir: Path) -> None:
        """Test that empty history returns default timezone."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="America/New_York")
        assert history.get_timezone_at(datetime(2024, 1, 1)) == "America/New_York"

    @pytest.mark.ai_generated
    def test_add_change_and_get_timezone(self, tmp_athlete_dir: Path) -> None:
        """Test adding a change and retrieving timezone."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        success, msg = history.add_change(
            datetime(2024, 6, 15, 12, 0, 0),
            "America/Los_Angeles",
            "gps:test",
        )
        assert success, msg

        # Before change: default timezone
        assert history.get_timezone_at(datetime(2024, 6, 15, 11, 0, 0)) == "UTC"

        # After change: new timezone
        assert history.get_timezone_at(datetime(2024, 6, 15, 13, 0, 0)) == "America/Los_Angeles"

    @pytest.mark.ai_generated
    def test_multiple_changes(self, tmp_athlete_dir: Path) -> None:
        """Test multiple timezone changes."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        # Add changes (out of order to test sorting)
        history.add_change_force(datetime(2024, 6, 20, 18, 0, 0), "America/New_York", "return")
        history.add_change_force(datetime(2024, 6, 15, 12, 0, 0), "America/Los_Angeles", "trip")

        # Before first change
        assert history.get_timezone_at(datetime(2024, 6, 1)) == "UTC"

        # During LA trip
        assert history.get_timezone_at(datetime(2024, 6, 17)) == "America/Los_Angeles"

        # After return
        assert history.get_timezone_at(datetime(2024, 6, 25)) == "America/New_York"

    @pytest.mark.ai_generated
    def test_save_and_load(self, tmp_athlete_dir: Path) -> None:
        """Test saving and loading history."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")
        history.add_change_force(datetime(2024, 6, 15, 12, 0, 0), "America/Los_Angeles", "test")
        history.save()

        # Load in new instance
        history2 = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")
        assert len(history2) == 1
        assert history2.get_timezone_at(datetime(2024, 6, 20)) == "America/Los_Angeles"

    @pytest.mark.ai_generated
    def test_get_local_time(self, tmp_athlete_dir: Path) -> None:
        """Test converting UTC to local time."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="America/New_York")

        # Winter time (EST = UTC-5)
        utc_time = datetime(2024, 1, 15, 17, 0, 0, tzinfo=ZoneInfo("UTC"))
        local_time = history.get_local_time(utc_time)
        assert local_time.hour == 12  # 17:00 UTC = 12:00 EST
        assert str(local_time.tzinfo) == "America/New_York"

    @pytest.mark.ai_generated
    def test_get_local_time_with_dst(self, tmp_athlete_dir: Path) -> None:
        """Test local time conversion respects DST."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="America/New_York")

        # Summer time (EDT = UTC-4)
        utc_time = datetime(2024, 7, 15, 17, 0, 0, tzinfo=ZoneInfo("UTC"))
        local_time = history.get_local_time(utc_time)
        assert local_time.hour == 13  # 17:00 UTC = 13:00 EDT

    @pytest.mark.ai_generated
    def test_reject_rapid_change(self, tmp_athlete_dir: Path) -> None:
        """Test that rapid timezone changes are rejected."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        # Add first change
        success, _ = history.add_change(
            datetime(2024, 6, 15, 12, 0, 0),
            "America/Los_Angeles",
            "first",
        )
        assert success

        # Try to add change within 4 hours - should fail
        success, msg = history.add_change(
            datetime(2024, 6, 15, 14, 0, 0),  # Only 2 hours later
            "America/Chicago",
            "rapid",
        )
        assert not success
        assert "Too close" in msg

    @pytest.mark.ai_generated
    def test_force_allows_rapid_change(self, tmp_athlete_dir: Path) -> None:
        """Test that force bypasses rapid change check."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        history.add_change_force(datetime(2024, 6, 15, 12, 0, 0), "America/Los_Angeles", "first")
        success, _ = history.add_change_force(
            datetime(2024, 6, 15, 14, 0, 0),  # Only 2 hours later
            "America/Chicago",
            "forced",
        )
        assert success

    @pytest.mark.ai_generated
    def test_reject_invalid_timezone(self, tmp_athlete_dir: Path) -> None:
        """Test that invalid timezone names are rejected."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        success, msg = history.add_change(
            datetime(2024, 6, 15, 12, 0, 0),
            "Invalid/Timezone",
            "test",
        )
        assert not success
        assert "Invalid timezone" in msg

    @pytest.mark.ai_generated
    def test_reject_no_change(self, tmp_athlete_dir: Path) -> None:
        """Test that adding same timezone is rejected."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="America/New_York")

        success, msg = history.add_change(
            datetime(2024, 6, 15, 12, 0, 0),
            "America/New_York",  # Same as default
            "test",
        )
        assert not success
        assert "Already in timezone" in msg

    @pytest.mark.ai_generated
    def test_clear(self, tmp_athlete_dir: Path) -> None:
        """Test clearing history."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")
        history.add_change_force(datetime(2024, 6, 15, 12, 0, 0), "America/Los_Angeles", "test")
        assert len(history) == 1

        history.clear()
        assert len(history) == 0


class TestTimezoneDetection:
    """Tests for GPS-based timezone detection."""

    @pytest.mark.ai_generated
    def test_detect_timezone_new_york(self) -> None:
        """Test detecting timezone for New York coordinates."""
        # Skip if timezonefinder not installed
        pytest.importorskip("timezonefinder")

        tz = detect_timezone_from_coords(lat=40.7128, lng=-74.0060)  # NYC
        assert tz == "America/New_York"

    @pytest.mark.ai_generated
    def test_detect_timezone_los_angeles(self) -> None:
        """Test detecting timezone for Los Angeles coordinates."""
        pytest.importorskip("timezonefinder")

        tz = detect_timezone_from_coords(lat=34.0522, lng=-118.2437)  # LA
        assert tz == "America/Los_Angeles"

    @pytest.mark.ai_generated
    def test_detect_timezone_london(self) -> None:
        """Test detecting timezone for London coordinates."""
        pytest.importorskip("timezonefinder")

        tz = detect_timezone_from_coords(lat=51.5074, lng=-0.1278)  # London
        assert tz == "Europe/London"

    @pytest.mark.ai_generated
    def test_detect_timezone_invalid_coords(self) -> None:
        """Test that invalid coordinates return None."""
        tz = detect_timezone_from_coords(lat=91.0, lng=0.0)  # Invalid lat
        assert tz is None

        tz = detect_timezone_from_coords(lat=0.0, lng=181.0)  # Invalid lng
        assert tz is None

    @pytest.mark.ai_generated
    def test_detect_timezone_null_island(self) -> None:
        """Test that Null Island (0,0) returns None (GPS error)."""
        tz = detect_timezone_from_coords(lat=0.0, lng=0.0)
        assert tz is None

        # Very close to Null Island
        tz = detect_timezone_from_coords(lat=0.05, lng=0.05)
        assert tz is None


class TestTimezoneValidation:
    """Tests for timezone history validation."""

    @pytest.mark.ai_generated
    def test_validate_rapid_changes(self, tmp_athlete_dir: Path) -> None:
        """Test that rapid changes are flagged."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        # Force add rapid changes
        history.add_change_force(datetime(2024, 6, 15, 12, 0, 0), "America/Los_Angeles", "1")
        history.add_change_force(datetime(2024, 6, 15, 13, 0, 0), "America/Chicago", "2")

        warnings = validate_timezone_history(history)
        assert len(warnings) >= 1
        assert any("Rapid" in w for w in warnings)

    @pytest.mark.ai_generated
    def test_validate_flickering(self, tmp_athlete_dir: Path) -> None:
        """Test that back-and-forth timezone changes are flagged."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        # Force add A -> B -> A pattern within 24 hours
        history.add_change_force(datetime(2024, 6, 15, 8, 0, 0), "America/New_York", "1")
        history.add_change_force(datetime(2024, 6, 15, 14, 0, 0), "America/Chicago", "2")
        history.add_change_force(datetime(2024, 6, 15, 20, 0, 0), "America/New_York", "3")

        warnings = validate_timezone_history(history)
        assert any("flickering" in w.lower() for w in warnings)

    @pytest.mark.ai_generated
    def test_validate_invalid_timezone_name(self, tmp_athlete_dir: Path) -> None:
        """Test that invalid timezone names are flagged."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        # Manually add invalid change (bypassing validation)
        history._changes.append(
            TimezoneChange(
                datetime_utc=datetime(2024, 6, 15, 12, 0, 0),
                timezone="Invalid/Zone",
                source="test",
            )
        )

        warnings = validate_timezone_history(history)
        assert any("Invalid timezone" in w for w in warnings)

    @pytest.mark.ai_generated
    def test_validate_empty_history(self, tmp_athlete_dir: Path) -> None:
        """Test that empty history has no warnings."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")
        warnings = validate_timezone_history(history)
        assert len(warnings) == 0


class TestTimezoneEdgeCases:
    """Tests for edge cases in timezone handling."""

    @pytest.mark.ai_generated
    def test_dst_transition_same_location(self, tmp_athlete_dir: Path) -> None:
        """Test that DST transitions are handled correctly without adding changes."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="America/New_York")

        # March 10, 2024 - DST starts (2 AM -> 3 AM)
        # The timezone name stays the same, only the offset changes
        before_dst = datetime(2024, 3, 10, 6, 0, 0, tzinfo=ZoneInfo("UTC"))  # 1 AM EST
        after_dst = datetime(2024, 3, 10, 8, 0, 0, tzinfo=ZoneInfo("UTC"))   # 4 AM EDT

        before_local = history.get_local_time(before_dst)
        after_local = history.get_local_time(after_dst)

        # Before: 6 AM UTC = 1 AM EST (UTC-5)
        assert before_local.hour == 1
        # After: 8 AM UTC = 4 AM EDT (UTC-4)
        assert after_local.hour == 4

        # Both should report same timezone name
        assert str(before_local.tzinfo) == "America/New_York"
        assert str(after_local.tzinfo) == "America/New_York"

    @pytest.mark.ai_generated
    def test_aware_datetime_input(self, tmp_athlete_dir: Path) -> None:
        """Test handling of timezone-aware datetime input."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="America/New_York")

        # Add change with aware datetime
        dt_aware = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
        success, _ = history.add_change(dt_aware, "America/Los_Angeles", "test")
        assert success

        # Query with aware datetime
        tz = history.get_timezone_at(datetime(2024, 6, 20, 0, 0, 0, tzinfo=ZoneInfo("UTC")))
        assert tz == "America/Los_Angeles"

    @pytest.mark.ai_generated
    def test_exact_boundary_time(self, tmp_athlete_dir: Path) -> None:
        """Test timezone lookup at exact change boundary."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")
        history.add_change_force(
            datetime(2024, 6, 15, 12, 0, 0),
            "America/New_York",
            "test",
        )

        # Exactly at change time should use new timezone
        tz = history.get_timezone_at(datetime(2024, 6, 15, 12, 0, 0))
        assert tz == "America/New_York"

        # One second before should use old timezone
        tz = history.get_timezone_at(datetime(2024, 6, 15, 11, 59, 59))
        assert tz == "UTC"

    @pytest.mark.ai_generated
    def test_iteration_and_length(self, tmp_athlete_dir: Path) -> None:
        """Test that history is iterable and has correct length."""
        history = TimezoneHistory(tmp_athlete_dir, default_timezone="UTC")

        assert len(history) == 0

        history.add_change_force(datetime(2024, 1, 1), "America/New_York", "1")
        history.add_change_force(datetime(2024, 6, 1), "America/Los_Angeles", "2")

        assert len(history) == 2

        timezones = [c.timezone for c in history]
        assert timezones == ["America/New_York", "America/Los_Angeles"]
