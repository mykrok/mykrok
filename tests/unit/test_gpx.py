"""Unit tests for GPX generation."""

from __future__ import annotations

import pytest

from mykrok.lib.gpx import get_gpx_size, simplify_track


@pytest.mark.ai_generated
class TestGPXUtils:
    """Tests for GPX utility functions."""

    def test_get_gpx_size(self) -> None:
        """Test GPX size calculation."""
        content = '<?xml version="1.0"?><gpx></gpx>'
        size = get_gpx_size(content)

        assert size == len(content.encode("utf-8"))

    def test_simplify_track_no_simplification(self) -> None:
        """Test track simplification when under limit."""
        points = [{"lat": i, "lng": i} for i in range(100)]
        result = simplify_track(points, max_points=200)

        assert len(result) == 100

    def test_simplify_track_with_simplification(self) -> None:
        """Test track simplification when over limit."""
        points = [{"lat": i, "lng": i} for i in range(1000)]
        result = simplify_track(points, max_points=100)

        assert len(result) <= 100
        # First and last points should be preserved
        assert result[0]["lat"] == 0
        assert result[-1]["lat"] == 999
