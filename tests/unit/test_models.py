"""Unit tests for data models."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from mykrok.models.activity import (
    Activity,
    load_activity,
    save_activity,
)
from mykrok.models.athlete import Athlete, Gear, GearCatalog
from mykrok.models.state import (
    FitTrackeeExportState,
    SyncState,
)


@pytest.mark.ai_generated
class TestActivity:
    """Tests for Activity model."""

    def test_activity_to_dict(self, sample_activity: dict) -> None:
        """Test Activity.to_dict() conversion."""
        activity = Activity(
            id=sample_activity["id"],
            name=sample_activity["name"],
            type=sample_activity["type"],
            sport_type=sample_activity["sport_type"],
            start_date=datetime.fromisoformat(sample_activity["start_date"].replace("Z", "+00:00")),
            start_date_local=datetime.fromisoformat(sample_activity["start_date_local"]),
            timezone=sample_activity["timezone"],
            distance=sample_activity["distance"],
            moving_time=sample_activity["moving_time"],
            elapsed_time=sample_activity["elapsed_time"],
        )

        result = activity.to_dict()

        assert result["id"] == sample_activity["id"]
        assert result["name"] == sample_activity["name"]
        assert result["type"] == sample_activity["type"]

    def test_activity_from_dict(self, sample_activity: dict) -> None:
        """Test Activity.from_dict() creation."""
        activity = Activity.from_dict(sample_activity)

        assert activity.id == sample_activity["id"]
        assert activity.name == sample_activity["name"]
        assert activity.distance == sample_activity["distance"]

    def test_save_and_load_activity(self, temp_data_dir: Path, sample_activity: dict) -> None:
        """Test saving and loading activity."""
        activity = Activity.from_dict(sample_activity)
        username = "test_athlete"

        # Save activity
        save_activity(temp_data_dir, username, activity)

        # Load it back
        from mykrok.lib.paths import get_session_dir

        session_dir = get_session_dir(temp_data_dir, username, activity.start_date)
        loaded = load_activity(session_dir)

        assert loaded is not None
        assert loaded.id == activity.id
        assert loaded.name == activity.name


@pytest.mark.ai_generated
class TestAthlete:
    """Tests for Athlete model."""

    def test_athlete_to_dict(self, sample_athlete: dict) -> None:
        """Test Athlete.to_dict() conversion."""
        athlete = Athlete(
            id=sample_athlete["id"],
            username=sample_athlete["username"],
            firstname=sample_athlete.get("firstname"),
            lastname=sample_athlete.get("lastname"),
        )

        result = athlete.to_dict()

        assert result["id"] == sample_athlete["id"]
        assert result["username"] == sample_athlete["username"]

    def test_gear_catalog(self, sample_gear: list) -> None:
        """Test GearCatalog operations."""
        catalog = GearCatalog()

        for g in sample_gear:
            gear = Gear.from_dict(g)
            catalog.add_or_update(gear)

        assert len(catalog.items) == 2
        assert catalog.get("g12345") is not None
        assert catalog.get("nonexistent") is None


@pytest.mark.ai_generated
class TestState:
    """Tests for state tracking."""

    def test_sync_state_to_dict(self) -> None:
        """Test SyncState.to_dict() conversion."""
        state = SyncState(
            last_sync=datetime(2025, 12, 18, 10, 0, 0),
            last_activity_date=datetime(2025, 12, 17, 6, 30, 0),
            total_activities=100,
        )

        result = state.to_dict()

        assert result["total_activities"] == 100
        assert "2025-12-18" in result["last_sync"]

    def test_fittrackee_export_state(self) -> None:
        """Test FitTrackee export state tracking."""
        state = FitTrackeeExportState(fittrackee_url="https://example.com")

        # Record an export
        state.record_export("20251218T063000", 123)

        assert state.is_exported("20251218T063000")
        assert not state.is_exported("20251217T180000")

        entry = state.get_export("20251218T063000")
        assert entry is not None
        assert entry.ft_workout_id == 123
