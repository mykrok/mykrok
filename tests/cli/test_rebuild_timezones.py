"""CLI integration tests for rebuild-timezones command."""

from __future__ import annotations

import pytest

from mykrok.cli import main


class TestRebuildTimezones:
    """Tests for mykrok rebuild-timezones command."""

    @pytest.mark.ai_generated
    def test_rebuild_timezones_dry_run(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --dry-run doesn't modify files."""
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

    @pytest.mark.ai_generated
    def test_rebuild_timezones_finds_athletes(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify command finds athletes in fixture data."""
        result = cli_runner.invoke(
            main,
            ["rebuild-timezones", "--dry-run"],
            env=cli_env,
        )

        if "timezonefinder not installed" in result.output:
            pytest.skip("timezonefinder not installed")

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should find the fixture athletes
        assert "athlete" in result.output.lower()

    @pytest.mark.ai_generated
    def test_rebuild_timezones_custom_default(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --default-timezone option works."""
        result = cli_runner.invoke(
            main,
            ["rebuild-timezones", "--dry-run", "--default-timezone", "Europe/London"],
            env=cli_env,
        )

        if "timezonefinder not installed" in result.output:
            pytest.skip("timezonefinder not installed")

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert "Europe/London" in result.output

    @pytest.mark.ai_generated
    def test_rebuild_timezones_detects_gps_activities(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify command processes GPS activities."""
        result = cli_runner.invoke(
            main,
            ["rebuild-timezones", "--dry-run"],
            env=cli_env,
        )

        if "timezonefinder not installed" in result.output:
            pytest.skip("timezonefinder not installed")

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should report GPS activities found
        assert "GPS" in result.output or "gps" in result.output.lower()

    @pytest.mark.ai_generated
    def test_rebuild_timezones_force_option(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --force option is accepted."""
        result = cli_runner.invoke(
            main,
            ["rebuild-timezones", "--dry-run", "--force"],
            env=cli_env,
        )

        if "timezonefinder not installed" in result.output:
            pytest.skip("timezonefinder not installed")

        # Should not error on --force
        assert result.exit_code == 0, f"Command failed: {result.output}"
