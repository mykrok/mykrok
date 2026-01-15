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
    def test_create_browser_generates_html(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify create-browser generates the HTML file in data directory."""
        result = cli_runner.invoke(
            main,
            ["create-browser"],  # Uses default filename mykrok.html
            env=cli_env,
        )

        assert (
            result.exit_code == 0
        ), f"Command failed (exit={result.exit_code}): {result.output}\nException: {result.exception}"
        # Output goes to data directory
        assert (cli_data_dir / "mykrok.html").exists(), "mykrok.html not created"

    @pytest.mark.ai_generated
    def test_create_browser_copies_javascript_assets(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify JavaScript assets are copied to data/assets."""
        result = cli_runner.invoke(
            main,
            ["create-browser"],
            env=cli_env,
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

        # Assets are copied to data_dir/assets/{leaflet,hyparquet,map-browser}
        assets_dir = cli_data_dir / "assets"
        assert assets_dir.exists(), "Assets directory not created"
        # JS files are in subdirectories
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

    @pytest.mark.ai_generated
    def test_create_browser_includes_data_references(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify generated HTML references session data."""
        result = cli_runner.invoke(
            main,
            ["create-browser"],
            env=cli_env,
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

        html_content = (cli_data_dir / "mykrok.html").read_text()
        # The browser should reference sessions data somehow
        assert (
            "sessions" in html_content.lower()
            or "athletes" in html_content.lower()
        ), "No data references found in HTML"

    @pytest.mark.ai_generated
    def test_create_browser_valid_html(
        self, cli_runner, cli_data_dir: Path, cli_env: dict[str, str]
    ) -> None:
        """Verify generated HTML is well-formed."""
        result = cli_runner.invoke(
            main,
            ["create-browser"],
            env=cli_env,
        )

        assert result.exit_code == 0, f"Command failed: {result.output}"

        html_content = (cli_data_dir / "mykrok.html").read_text()
        # Basic HTML structure checks
        assert "<html" in html_content.lower(), "Missing <html> tag"
        assert "<head" in html_content.lower(), "Missing <head> tag"
        assert "<body" in html_content.lower(), "Missing <body> tag"
