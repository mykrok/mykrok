"""Tests for gh-pages generation."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repository for testing."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


@pytest.mark.ai_generated
class TestGhPagesGeneration:
    """Tests for gh-pages generation functionality."""

    def test_generate_gh_pages_creates_branch(self, git_repo: Path) -> None:
        """Test that generate_gh_pages creates the gh-pages branch."""
        from mykrok.services.gh_pages import generate_gh_pages

        worktree_path = git_repo / ".gh-pages"

        results = generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )

        assert results["is_new_branch"] is True
        assert results["had_changes"] is True
        assert results["pushed"] is False

        # Verify branch exists
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "gh-pages"],
            cwd=git_repo,
            capture_output=True,
        )
        assert result.returncode == 0

    def test_generate_gh_pages_has_expected_files(self, git_repo: Path) -> None:
        """Test that gh-pages branch contains all expected files."""
        from mykrok.services.gh_pages import (
            generate_gh_pages,
            get_expected_files,
        )

        worktree_path = git_repo / ".gh-pages"

        generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )

        # Check files in gh-pages branch using git show
        expected_files = get_expected_files()
        for filepath in expected_files:
            result = subprocess.run(
                ["git", "show", f"gh-pages:{filepath}"],
                cwd=git_repo,
                capture_output=True,
            )
            assert result.returncode == 0, f"Missing file in gh-pages: {filepath}"

    def test_generate_gh_pages_is_idempotent(self, git_repo: Path) -> None:
        """Test that running twice produces no new commit."""
        from mykrok.services.gh_pages import generate_gh_pages

        worktree_path = git_repo / ".gh-pages"

        # First run - should create branch and commit
        results1 = generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )
        assert results1["is_new_branch"] is True
        assert results1["had_changes"] is True

        # Get commit hash after first run
        result = subprocess.run(
            ["git", "rev-parse", "gh-pages"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        commit1 = result.stdout.strip()

        # Second run - should NOT create new commit (same content)
        results2 = generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )
        assert results2["is_new_branch"] is False
        assert results2["had_changes"] is False

        # Get commit hash after second run
        result = subprocess.run(
            ["git", "rev-parse", "gh-pages"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        commit2 = result.stdout.strip()

        # Commits should be the same (no new commit)
        assert commit1 == commit2, "Second run created a new commit when it shouldn't have"

    def test_generate_gh_pages_different_seed_produces_different_content(
        self, git_repo: Path
    ) -> None:
        """Test that different seeds produce different content."""
        from mykrok.services.gh_pages import generate_gh_pages

        worktree_path = git_repo / ".gh-pages"

        # First run with seed 42
        generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )

        # Get content hash after first run
        result = subprocess.run(
            ["git", "rev-parse", "gh-pages^{tree}"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        tree1 = result.stdout.strip()

        # Second run with different seed - should create new commit
        results2 = generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=123,
        )
        assert results2["had_changes"] is True

        # Get content hash after second run
        result = subprocess.run(
            ["git", "rev-parse", "gh-pages^{tree}"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        tree2 = result.stdout.strip()

        # Trees should be different (different content)
        assert tree1 != tree2, "Different seeds produced identical content"

    def test_generate_gh_pages_index_html_exists(self, git_repo: Path) -> None:
        """Test that index.html is properly generated."""
        from mykrok.services.gh_pages import generate_gh_pages

        worktree_path = git_repo / ".gh-pages"

        generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )

        # Get index.html content
        result = subprocess.run(
            ["git", "show", "gh-pages:index.html"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        html_content = result.stdout

        # Verify it's a valid HTML file with expected content
        assert "<!DOCTYPE html>" in html_content
        assert "mykrok" in html_content.lower()
        assert "leaflet" in html_content.lower()

    def test_generate_gh_pages_readme_exists(self, git_repo: Path) -> None:
        """Test that README.md is properly generated."""
        from mykrok.services.gh_pages import generate_gh_pages

        worktree_path = git_repo / ".gh-pages"

        generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )

        # Get README.md content
        result = subprocess.run(
            ["git", "show", "gh-pages:README.md"],
            cwd=git_repo,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        readme_content = result.stdout

        # Verify expected content
        assert "MyKrok Demo" in readme_content
        assert "DataLad" in readme_content
        assert "synthetic data" in readme_content

    def test_generate_gh_pages_cleans_up_worktree(self, git_repo: Path) -> None:
        """Test that worktree is cleaned up after generation."""
        from mykrok.services.gh_pages import generate_gh_pages

        worktree_path = git_repo / ".gh-pages"

        generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )

        # Worktree should not exist after completion
        assert not worktree_path.exists(), "Worktree was not cleaned up"

        # But branch should exist
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "gh-pages"],
            cwd=git_repo,
            capture_output=True,
        )
        assert result.returncode == 0


@pytest.mark.ai_generated
class TestVerifyGhPagesContent:
    """Tests for gh-pages content verification."""

    def test_verify_content_all_present(self, git_repo: Path) -> None:
        """Test verification when all files are present."""
        from mykrok.services.gh_pages import (
            generate_gh_pages,
            get_expected_files,
        )

        worktree_path = git_repo / ".gh-pages"

        generate_gh_pages(
            repo_root=git_repo,
            worktree_path=worktree_path,
            push=False,
            use_datalad=False,
            seed=42,
        )

        # Verify all expected files exist in the branch
        expected = get_expected_files()
        for filepath in expected:
            result = subprocess.run(
                ["git", "show", f"gh-pages:{filepath}"],
                cwd=git_repo,
                capture_output=True,
            )
            assert result.returncode == 0, f"Expected file missing: {filepath}"
