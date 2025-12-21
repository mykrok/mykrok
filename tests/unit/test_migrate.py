"""Tests for migrate module."""

from __future__ import annotations

from pathlib import Path

import pytest

from strava_backup.services.migrate import (
    LOG_GITATTRIBUTES_RULE,
    add_log_gitattributes_rule,
)


@pytest.mark.ai_generated
class TestAddLogGitattributesRule:
    """Tests for add_log_gitattributes_rule function."""

    def test_adds_rule_to_new_file(self, tmp_path: Path) -> None:
        """Test adding rule when .gitattributes doesn't exist."""
        result = add_log_gitattributes_rule(tmp_path)

        assert result is True
        gitattributes = tmp_path / ".gitattributes"
        assert gitattributes.exists()
        content = gitattributes.read_text()
        assert "*.log annex.largefiles=anything" in content

    def test_adds_rule_to_existing_file(self, tmp_path: Path) -> None:
        """Test adding rule to existing .gitattributes."""
        gitattributes = tmp_path / ".gitattributes"
        gitattributes.write_text("*.jpg annex.largefiles=anything\n")

        result = add_log_gitattributes_rule(tmp_path)

        assert result is True
        content = gitattributes.read_text()
        assert "*.jpg annex.largefiles=anything" in content
        assert "*.log annex.largefiles=anything" in content

    def test_skips_if_rule_already_present(self, tmp_path: Path) -> None:
        """Test skipping if rule already exists."""
        gitattributes = tmp_path / ".gitattributes"
        gitattributes.write_text(LOG_GITATTRIBUTES_RULE)
        original_content = gitattributes.read_text()

        result = add_log_gitattributes_rule(tmp_path)

        assert result is False
        # Content should not be modified at all
        assert gitattributes.read_text() == original_content

    def test_dry_run_does_not_modify(self, tmp_path: Path) -> None:
        """Test dry run mode doesn't create/modify files."""
        result = add_log_gitattributes_rule(tmp_path, dry_run=True)

        assert result is True
        gitattributes = tmp_path / ".gitattributes"
        assert not gitattributes.exists()

    def test_dry_run_existing_file_no_rule(self, tmp_path: Path) -> None:
        """Test dry run with existing file that needs the rule."""
        gitattributes = tmp_path / ".gitattributes"
        original_content = "*.jpg annex.largefiles=anything\n"
        gitattributes.write_text(original_content)

        result = add_log_gitattributes_rule(tmp_path, dry_run=True)

        assert result is True
        # Content should not be modified
        assert gitattributes.read_text() == original_content
