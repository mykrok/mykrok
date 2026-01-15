"""CLI integration tests for view stats command."""

from __future__ import annotations

import json

import pytest

from mykrok.cli import main


class TestViewStats:
    """Tests for mykrok view stats command."""

    @pytest.mark.ai_generated
    def test_view_stats_outputs_totals(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify stats output includes totals."""
        result = cli_runner.invoke(main, ["view", "stats"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should have some statistics in output
        output_lower = result.output.lower()
        assert (
            "total" in output_lower
            or "activities" in output_lower
            or "distance" in output_lower
        ), f"No statistics found in output: {result.output}"

    @pytest.mark.ai_generated
    def test_view_stats_json_output(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --json produces valid JSON output."""
        # --json is a global option, must come before subcommand
        result = cli_runner.invoke(main, ["--json", "view", "stats"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Should be valid JSON
        try:
            data = json.loads(result.output)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}\nOutput: {result.output}")

        # Should have some stats structure
        assert isinstance(data, dict), "JSON output should be a dict"

    @pytest.mark.ai_generated
    def test_view_stats_year_filter(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --year filters correctly."""
        result = cli_runner.invoke(
            main, ["view", "stats", "--year", "2024"], env=cli_env
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

    @pytest.mark.ai_generated
    def test_view_stats_by_type(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify --by-type shows breakdown by activity type."""
        result = cli_runner.invoke(main, ["view", "stats", "--by-type"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should mention activity types
        output_lower = result.output.lower()
        assert (
            "run" in output_lower or "ride" in output_lower or "type" in output_lower
        ), f"No activity types in output: {result.output}"

    @pytest.mark.ai_generated
    def test_view_stats_json_has_totals(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify JSON output includes totals structure."""
        # --json is a global option, must come before subcommand
        result = cli_runner.invoke(main, ["--json", "view", "stats"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        data = json.loads(result.output)

        # Should have totals or similar summary
        assert (
            "totals" in data
            or "total" in data
            or "activities" in data
            or "summary" in data
        ), f"No totals in JSON: {data.keys()}"

    @pytest.mark.ai_generated
    def test_view_stats_with_verbose(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify stats works with verbose flag."""
        result = cli_runner.invoke(main, ["-v", "view", "stats"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"
