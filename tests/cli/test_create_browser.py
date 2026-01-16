"""CLI integration tests for create-browser command.

Note: The create-browser command outputs to the DATA directory (not a custom output dir).
The -o option specifies the filename (default: mykrok.html), not the output directory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mykrok.cli import main


class TestCreateBrowser:
    """Tests for mykrok create-browser command."""

    @pytest.mark.ai_generated
    def test_create_browser_generates_valid_html_with_assets(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify create-browser generates valid HTML with proper structure and assets.

        This consolidated test verifies:
        - Command exits successfully
        - HTML file is created in data directory
        - HTML has valid structure (<html>, <head>, <body>)
        - HTML references session/athlete data
        - JavaScript assets are copied to assets directory
        """
        result = cli_runner.invoke(
            main,
            ["create-browser"],  # Uses default filename mykrok.html
            env=cli_env,
        )

        # Verify command succeeded
        assert (
            result.exit_code == 0
        ), f"Command failed (exit={result.exit_code}): {result.output}\nException: {result.exception}"

        # Verify HTML file created
        html_file = cli_data_dir / "mykrok.html"
        assert html_file.exists(), "mykrok.html not created"

        # Verify HTML structure
        html_content = html_file.read_text()
        assert "<html" in html_content.lower(), "Missing <html> tag"
        assert "<head" in html_content.lower(), "Missing <head> tag"
        assert "<body" in html_content.lower(), "Missing <body> tag"

        # Verify data references
        assert (
            "sessions" in html_content.lower() or "athletes" in html_content.lower()
        ), "No data references found in HTML"

        # Verify JavaScript assets copied
        assets_dir = cli_data_dir / "assets"
        assert assets_dir.exists(), "Assets directory not created"
        js_files = list(assets_dir.glob("**/*.js"))
        assert len(js_files) > 0, f"No JavaScript files in {assets_dir} subdirectories"

    @pytest.mark.ai_generated
    def test_create_browser_custom_filename(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify custom output filename works."""
        result = cli_runner.invoke(
            main,
            ["create-browser", "-o", "custom_browser.html"],
            env=cli_env,
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"
        assert (cli_data_dir / "custom_browser.html").exists(), "Custom file not created"
