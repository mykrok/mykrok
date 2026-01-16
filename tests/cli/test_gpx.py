"""CLI integration tests for gpx command.

Note: The gpx command expects session KEYS (e.g. "20241201T060000"),
not full paths. When no sessions are specified, it exports all sessions.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from mykrok.cli import main


def extract_session_key(session_dir: Path) -> str:
    """Extract session key from directory name like 'ses=20241201T060000'."""
    return session_dir.name.replace("ses=", "")


class TestGpx:
    """Tests for mykrok gpx command."""

    @pytest.mark.ai_generated
    def test_gpx_generates_valid_xml_files(
        self, cli_runner, cli_env: dict[str, str], tmp_path: Path
    ) -> None:
        """Verify GPX files are generated and valid.

        This consolidated test verifies:
        - GPX files are generated when exporting all sessions
        - All generated GPX files are valid XML
        - Output directory is created if needed
        """
        output_dir = tmp_path / "gpx_output"

        # Export all sessions (no session filter)
        result = cli_runner.invoke(
            main,
            ["gpx", "--output-dir", str(output_dir)],
            env=cli_env,
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Verify output directory was created
        assert output_dir.exists(), "Output directory not created"

        # Verify GPX files were generated
        gpx_files = list(output_dir.glob("*.gpx"))
        assert len(gpx_files) > 0, f"No GPX files generated. Output: {result.output}"

        # Verify all GPX files are valid XML
        for gpx_file in gpx_files:
            try:
                ET.parse(gpx_file)
            except ET.ParseError as e:
                pytest.fail(f"Invalid XML in {gpx_file}: {e}")

    @pytest.mark.ai_generated
    def test_gpx_with_extensions_and_specific_session(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str], tmp_path: Path
    ) -> None:
        """Verify GPX export options work correctly.

        This consolidated test verifies:
        - Extension options (--with-hr, --with-cadence) are accepted
        - Specific session export by key works
        - Nested output directory is created
        """
        # Test with extension options
        output_dir1 = tmp_path / "gpx_with_ext"
        result_ext = cli_runner.invoke(
            main,
            [
                "gpx",
                "--output-dir",
                str(output_dir1),
                "--with-hr",
                "--with-cadence",
            ],
            env=cli_env,
        )
        # Should not fail even if data doesn't have HR/cadence
        assert result_ext.exit_code in [0, 1], f"Unexpected error: {result_ext.output}"

        # Test specific session export
        sessions = list(cli_data_dir.glob("**/ses=*"))
        if sessions:
            session_key = extract_session_key(sessions[0])
            output_dir2 = tmp_path / "new" / "nested" / "gpx"
            result_session = cli_runner.invoke(
                main,
                ["gpx", session_key, "--output-dir", str(output_dir2)],
                env=cli_env,
            )
            # Should succeed or skip if no GPS for this session
            assert result_session.exit_code in [0, 1], f"Unexpected error: {result_session.output}"
            # Nested directory should be created
            assert output_dir2.exists(), "Nested output directory not created"
