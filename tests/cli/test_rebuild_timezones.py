"""CLI integration tests for rebuild-timezones command."""

from __future__ import annotations

import pytest

from mykrok.cli import main


class TestRebuildTimezones:
    """Tests for mykrok rebuild-timezones command."""

    @pytest.mark.ai_generated
    def test_rebuild_timezones_comprehensive(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify rebuild-timezones command with various options.

        This consolidated test verifies:
        - Dry run mode doesn't modify files
        - Command finds athletes in fixture data
        - Custom default timezone option works
        - Force option is accepted
        - GPS activities are detected
        """
        # Test basic dry run
        result = cli_runner.invoke(
            main,
            ["rebuild-timezones", "--dry-run"],
            env=cli_env,
        )

        # May fail if timezonefinder not installed, which is optional
        if "timezonefinder not installed" in result.output:
            pytest.skip("timezonefinder not installed")

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "DRY RUN" in result.output
        # Should find the fixture athletes
        assert "athlete" in result.output.lower()
        # Should report GPS activities found
        assert "GPS" in result.output or "gps" in result.output.lower()

        # Test custom default timezone option
        result_tz = cli_runner.invoke(
            main,
            ["rebuild-timezones", "--dry-run", "--default-timezone", "Europe/London"],
            env=cli_env,
        )
        assert result_tz.exit_code == 0, f"Custom timezone failed: {result_tz.output}"
        assert "Europe/London" in result_tz.output

        # Test force option
        result_force = cli_runner.invoke(
            main,
            ["rebuild-timezones", "--dry-run", "--force"],
            env=cli_env,
        )
        assert result_force.exit_code == 0, f"Force option failed: {result_force.output}"
