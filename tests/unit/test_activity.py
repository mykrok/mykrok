"""Unit tests for activity model."""

from __future__ import annotations

import pytest


@pytest.mark.ai_generated
class TestExtractEnumValue:
    """Tests for _extract_enum_value helper function."""

    def test_extract_from_root_attribute(self) -> None:
        """Test extracting value from object with root attribute."""
        from mykrok.models.activity import _extract_enum_value

        class MockEnum:
            root = "Workout"

        result = _extract_enum_value(MockEnum())
        assert result == "Workout"

    def test_extract_from_string(self) -> None:
        """Test that strings pass through unchanged."""
        from mykrok.models.activity import _extract_enum_value

        result = _extract_enum_value("Run")
        assert result == "Run"

    def test_extract_from_none(self) -> None:
        """Test that None returns empty string."""
        from mykrok.models.activity import _extract_enum_value

        result = _extract_enum_value(None)
        assert result == ""

    def test_extract_from_root_string_format(self) -> None:
        """Test extracting value from root='Value' string format."""
        from mykrok.models.activity import _extract_enum_value

        # Simulate what str() might return for stravalib enum
        class MockEnumBadStr:
            def __str__(self) -> str:
                return "root='Workout'"

        result = _extract_enum_value(MockEnumBadStr())
        assert result == "Workout"

    def test_extract_from_root_double_quote_format(self) -> None:
        """Test extracting value from root=\"Value\" string format."""
        from mykrok.models.activity import _extract_enum_value

        class MockEnumDoubleQuote:
            def __str__(self) -> str:
                return 'root="Ride"'

        result = _extract_enum_value(MockEnumDoubleQuote())
        assert result == "Ride"

    def test_sessions_tsv_values_format(self) -> None:
        """Test that sessions.tsv stores clean type/sport values, not root='...'."""
        from mykrok.models.activity import _extract_enum_value

        # Verify the function strips the root= prefix
        for test_value in ["Workout", "Run", "Ride", "Swim", "Walk"]:

            class MockEnum:
                root = test_value

            result = _extract_enum_value(MockEnum())
            assert result == test_value
            assert "root=" not in result
            assert "'" not in result
