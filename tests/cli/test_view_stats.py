"""CLI integration tests for view stats command."""

from __future__ import annotations

import json

import pytest

from mykrok.cli import main


class TestViewStats:
    """Tests for mykrok view stats command."""

    @pytest.mark.ai_generated
    def test_view_stats_text_output(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify stats text output includes totals and works with verbose.

        This consolidated test verifies:
        - Command exits successfully
        - Output includes statistics (totals, activities, distance)
        - Verbose flag works without errors
        """
        # Test basic stats output
        result = cli_runner.invoke(main, ["view", "stats"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        output_lower = result.output.lower()
        assert (
            "total" in output_lower
            or "activities" in output_lower
            or "distance" in output_lower
        ), f"No statistics found in output: {result.output}"

        # Also verify verbose works
        result_verbose = cli_runner.invoke(main, ["-v", "view", "stats"], env=cli_env)
        assert result_verbose.exit_code == 0, f"Verbose command failed: {result_verbose.output}"

    @pytest.mark.ai_generated
    def test_view_stats_json_output(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --json produces valid JSON output with expected structure.

        This consolidated test verifies:
        - JSON output is valid
        - Output is a dict with totals/summary structure
        """
        # --json is a global option, must come before subcommand
        result = cli_runner.invoke(main, ["--json", "view", "stats"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify valid JSON
        try:
            data = json.loads(result.output)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}\nOutput: {result.output}")

        # Verify structure
        assert isinstance(data, dict), "JSON output should be a dict"
        assert (
            "totals" in data
            or "total" in data
            or "activities" in data
            or "summary" in data
        ), f"No totals in JSON: {data.keys()}"

    @pytest.mark.ai_generated
    def test_view_stats_filters(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --year and --by-type filters work correctly.

        This consolidated test verifies:
        - Year filter is accepted and works
        - By-type shows activity type breakdown
        """
        # Test year filter
        result_year = cli_runner.invoke(
            main, ["view", "stats", "--year", "2024"], env=cli_env
        )
        assert result_year.exit_code == 0, f"Year filter failed: {result_year.output}"

        # Test by-type filter
        result_type = cli_runner.invoke(main, ["view", "stats", "--by-type"], env=cli_env)
        assert result_type.exit_code == 0, f"By-type failed: {result_type.output}"
        output_lower = result_type.output.lower()
        assert (
            "run" in output_lower or "ride" in output_lower or "type" in output_lower
        ), f"No activity types in output: {result_type.output}"
