"""CLI integration tests for migrate command."""

from __future__ import annotations

from pathlib import Path

import pytest

from mykrok.cli import main


class TestMigrate:
    """Tests for mykrok migrate command."""

    @pytest.mark.ai_generated
    def test_migrate_dry_run_no_changes(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify --dry-run makes no data file changes."""
        # Capture file modification times before (exclude logs directory)
        before_mtimes = {
            f: f.stat().st_mtime
            for f in cli_data_dir.rglob("*")
            if f.is_file() and "logs" not in str(f)
        }

        result = cli_runner.invoke(main, ["migrate", "--dry-run"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify no data files were modified (exclude logs)
        after_mtimes = {
            f: f.stat().st_mtime
            for f in cli_data_dir.rglob("*")
            if f.is_file() and "logs" not in str(f)
        }
        assert before_mtimes == after_mtimes, "Data files were modified during dry-run"

    @pytest.mark.ai_generated
    def test_migrate_idempotent(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify running migrate twice produces same result."""
        # First run
        result1 = cli_runner.invoke(main, ["migrate"], env=cli_env)
        assert result1.exit_code == 0, f"First run failed: {result1.output}"

        # Capture state after first run
        first_state = {
            f: f.read_bytes() for f in cli_data_dir.rglob("*.tsv") if f.is_file()
        }

        # Second run
        result2 = cli_runner.invoke(main, ["migrate"], env=cli_env)
        assert result2.exit_code == 0, f"Second run failed: {result2.output}"

        # Compare state
        second_state = {
            f: f.read_bytes() for f in cli_data_dir.rglob("*.tsv") if f.is_file()
        }
        assert first_state == second_state, "State changed between runs"

    @pytest.mark.ai_generated
    def test_migrate_succeeds_on_fresh_data(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify migrate succeeds on freshly generated fixture data."""
        result = cli_runner.invoke(main, ["migrate"], env=cli_env)

        # Should succeed (even if no migrations needed)
        assert result.exit_code == 0, f"Command failed: {result.output}"

    @pytest.mark.ai_generated
    def test_migrate_with_verbose(
        self, cli_runner, cli_env: dict[str, str]
    ) -> None:
        """Verify migrate works with verbose output."""
        result = cli_runner.invoke(main, ["-v", "migrate"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"
