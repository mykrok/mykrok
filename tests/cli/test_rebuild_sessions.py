"""CLI integration tests for rebuild-sessions command."""

from __future__ import annotations

from pathlib import Path

import pytest

from mykrok.cli import main


class TestRebuildSessions:
    """Tests for mykrok rebuild-sessions command."""

    @pytest.mark.ai_generated
    def test_rebuild_sessions_creates_complete_tsv(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify rebuild-sessions creates sessions.tsv with correct structure.

        This consolidated test verifies:
        - Sessions.tsv files are created
        - TSV has correct number of rows matching session directories
        - TSV includes all required columns
        - Command produces informative output
        """
        # Remove existing sessions.tsv files
        for tsv in cli_data_dir.glob("**/sessions.tsv"):
            tsv.unlink()

        # Verify they're gone
        assert not list(cli_data_dir.glob("**/sessions.tsv"))

        # Count session directories for alice before running
        alice_sessions = list((cli_data_dir / "athl=alice").glob("ses=*"))

        # Run rebuild-sessions
        result = cli_runner.invoke(main, ["rebuild-sessions"], env=cli_env)

        assert result.exit_code == 0, f"Command failed: {result.output}"
        # Should mention athletes found
        assert "athlete" in result.output.lower() or "session" in result.output.lower()

        # Verify sessions.tsv files were created
        sessions_files = list(cli_data_dir.glob("**/sessions.tsv"))
        assert len(sessions_files) > 0, "No sessions.tsv files created"

        # Check alice's sessions.tsv
        alice_tsv = cli_data_dir / "athl=alice" / "sessions.tsv"
        assert alice_tsv.exists(), "Alice's sessions.tsv not found"

        # Verify required columns in header
        lines = alice_tsv.read_text().strip().split("\n")
        header = lines[0]
        required_columns = [
            "datetime",
            "type",
            "sport",
            "name",
            "distance_m",
            "start_lat",
            "start_lng",
        ]
        for col in required_columns:
            assert col in header, f"Missing required column: {col}"

        # Verify row count (excluding header)
        row_count = len(lines) - 1
        assert row_count == len(
            alice_sessions
        ), f"Expected {len(alice_sessions)} rows, got {row_count}"

    @pytest.mark.ai_generated
    def test_rebuild_sessions_idempotent(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify running rebuild-sessions twice produces same result."""
        # First run
        result1 = cli_runner.invoke(main, ["rebuild-sessions"], env=cli_env)
        assert result1.exit_code == 0

        # Capture state after first run
        alice_tsv = cli_data_dir / "athl=alice" / "sessions.tsv"
        first_content = alice_tsv.read_text()

        # Second run
        result2 = cli_runner.invoke(main, ["rebuild-sessions"], env=cli_env)
        assert result2.exit_code == 0

        # Compare
        second_content = alice_tsv.read_text()
        assert first_content == second_content, "Sessions.tsv changed between runs"
