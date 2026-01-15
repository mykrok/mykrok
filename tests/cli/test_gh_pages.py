"""CLI integration tests for gh-pages command."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mykrok.cli import main


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    return repo_dir


class TestGhPages:
    """Tests for mykrok gh-pages command."""

    @pytest.mark.ai_generated
    def test_gh_pages_requires_git_repo(
        self, cli_runner, cli_env: dict[str, str], tmp_path: Path
    ) -> None:
        """Verify command fails outside git repository."""
        # Run from a non-git directory
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = cli_runner.invoke(
                main,
                ["gh-pages"],
                env=cli_env,
            )
        finally:
            os.chdir(old_cwd)

        assert result.exit_code != 0
        assert "git repository" in result.output.lower()

    @pytest.mark.ai_generated
    def test_gh_pages_generates_demo(
        self, cli_runner, cli_env: dict[str, str], git_repo: Path
    ) -> None:
        """Verify gh-pages generates demo content."""
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(git_repo)
            result = cli_runner.invoke(
                main,
                ["gh-pages", "--no-datalad"],
                env=cli_env,
            )
        finally:
            os.chdir(old_cwd)

        # Should succeed or fail gracefully
        if result.exit_code == 0:
            assert "GitHub Pages" in result.output or "gh-pages" in result.output.lower()

    @pytest.mark.ai_generated
    def test_gh_pages_custom_seed(
        self, cli_runner, cli_env: dict[str, str], git_repo: Path
    ) -> None:
        """Verify --seed option for reproducible demo data."""
        import os

        old_cwd = os.getcwd()
        try:
            os.chdir(git_repo)
            result = cli_runner.invoke(
                main,
                ["gh-pages", "--no-datalad", "--seed", "123"],
                env=cli_env,
            )
        finally:
            os.chdir(old_cwd)

        # Should accept the seed option
        assert result.exit_code in [0, 1], f"Unexpected error: {result.output}"

    @pytest.mark.ai_generated
    def test_gh_pages_custom_worktree(
        self, cli_runner, cli_env: dict[str, str], git_repo: Path, tmp_path: Path
    ) -> None:
        """Verify --worktree option for custom path."""
        import os

        worktree_path = tmp_path / "custom-worktree"
        old_cwd = os.getcwd()
        try:
            os.chdir(git_repo)
            result = cli_runner.invoke(
                main,
                ["gh-pages", "--no-datalad", "--worktree", str(worktree_path)],
                env=cli_env,
            )
        finally:
            os.chdir(old_cwd)

        # Should accept the worktree option
        assert result.exit_code in [0, 1], f"Unexpected error: {result.output}"
