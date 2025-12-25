"""GitHub Pages demo website generation.

Generates a gh-pages branch with a live demo of the MyKrok
web frontend using reproducible synthetic data.
"""

from __future__ import annotations

import random
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[Any]:
    """Run a command and optionally capture output."""
    kwargs: dict[str, Any] = {"cwd": cwd, "check": check}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def branch_exists(branch: str, cwd: Path | None = None) -> bool:
    """Check if a git branch exists locally."""
    result = run_cmd(
        ["git", "rev-parse", "--verify", branch],
        cwd=cwd,
        check=False,
        capture=True,
    )
    return result.returncode == 0


def remote_branch_exists(branch: str, remote: str = "origin", cwd: Path | None = None) -> bool:
    """Check if a branch exists on remote."""
    result = run_cmd(
        ["git", "ls-remote", "--heads", remote, branch],
        cwd=cwd,
        check=False,
        capture=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def fetch_remote_branch(branch: str, remote: str = "origin", cwd: Path | None = None) -> bool:
    """Fetch a branch from remote.

    Args:
        branch: Branch name to fetch.
        remote: Remote name (default: origin).
        cwd: Working directory.

    Returns:
        True if fetch succeeded.
    """
    result = run_cmd(
        ["git", "fetch", remote, f"{branch}:{branch}"],
        cwd=cwd,
        check=False,
        capture=True,
    )
    return result.returncode == 0


def has_datalad() -> bool:
    """Check if datalad is available."""
    result = run_cmd(["which", "datalad"], check=False, capture=True)
    return result.returncode == 0


def setup_worktree(
    repo_root: Path,
    worktree_path: Path,
    branch: str = "gh-pages",
) -> bool:
    """Set up git worktree for gh-pages branch.

    Args:
        repo_root: Path to the git repository root.
        worktree_path: Path for the worktree.
        branch: Branch name (default: gh-pages).

    Returns:
        True if branch was newly created (orphan).
    """
    # Clean up any existing worktree
    if worktree_path.exists():
        run_cmd(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=repo_root,
            check=False,
        )
        if worktree_path.exists():
            shutil.rmtree(worktree_path)

    # Check if branch exists locally
    has_local = branch_exists(branch, cwd=repo_root)

    # If not local, check remote and fetch if exists
    if not has_local and remote_branch_exists(branch, cwd=repo_root):
        fetch_remote_branch(branch, cwd=repo_root)
        has_local = branch_exists(branch, cwd=repo_root)

    is_new = not has_local

    if is_new:
        # Create orphan branch
        run_cmd(
            ["git", "worktree", "add", "--detach", str(worktree_path)],
            cwd=repo_root,
        )

        # Create orphan branch in worktree
        run_cmd(["git", "checkout", "--orphan", branch], cwd=worktree_path)
        run_cmd(["git", "reset", "--hard"], cwd=worktree_path)

        # Create initial empty commit
        run_cmd(
            ["git", "commit", "--allow-empty", "-m", "Initial gh-pages branch"],
            cwd=worktree_path,
        )
    else:
        # Use existing branch
        run_cmd(
            ["git", "worktree", "add", str(worktree_path), branch],
            cwd=repo_root,
        )

    return is_new


def clean_worktree(worktree_path: Path) -> None:
    """Remove all files from worktree except .git."""
    for item in worktree_path.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def generate_demo_data(output_dir: Path, seed: int = 42) -> dict[str, Any]:
    """Generate reproducible demo data.

    Args:
        output_dir: Directory to generate data in.
        seed: Random seed for reproducibility.

    Returns:
        Dictionary with generation results.
    """
    import sys

    # Try to import generate_fixtures from tests
    # This works when running from the repo or in development
    try:
        from tests.e2e.fixtures.generate_fixtures import generate_fixtures
    except ImportError:
        # Try to find the repo root and add tests to path
        repo_root = Path(__file__).parent.parent.parent.parent
        tests_path = repo_root / "tests" / "e2e" / "fixtures"
        if tests_path.exists():
            sys.path.insert(0, str(tests_path))
            from generate_fixtures import generate_fixtures  # type: ignore[no-redef]
        else:
            raise ImportError(
                "Cannot find generate_fixtures. "
                "This command must be run from within the mykrok repository."
            ) from None

    random.seed(seed)
    generate_fixtures(output_dir)

    return {
        "athletes_tsv": output_dir / "athletes.tsv",
        "seed": seed,
    }


def generate_html(data_dir: Path) -> Path:
    """Generate the lightweight HTML file and copy assets.

    Args:
        data_dir: Directory containing the data.

    Returns:
        Path to the generated index.html.
    """
    from mykrok.views.map import copy_assets_to_output, generate_browser

    html = generate_browser(data_dir)
    html_path = data_dir / "index.html"
    html_path.write_text(html, encoding="utf-8")
    copy_assets_to_output(data_dir)

    return html_path


GH_PAGES_README = """\
# MyKrok Demo

This is a live demo of the [MyKrok](https://github.com/mykrok/mykrok)
web frontend using synthetic data.

**[View Demo](https://mykrok.github.io/mykrok/)**

## About

This demo showcases the lightweight web frontend that provides:
- Interactive map with activity markers
- Sessions list with filtering and search
- Session detail view with GPS track
- Statistics dashboard with charts

## Note

This demo uses synthetic data generated for illustration purposes.
The data structure follows the MyKrok format but does not contain
real Strava activities.

While this branch is managed as a DataLad dataset for reproducibility,
you do **not** need DataLad or git-annex to clone or view this demo.
A simple `git clone` works fine.

---
*Auto-generated by `mykrok gh-pages`*
"""


def create_readme(output_dir: Path) -> Path:
    """Create README for gh-pages branch.

    Args:
        output_dir: Directory to create README in.

    Returns:
        Path to the created README.
    """
    readme_path = output_dir / "README.md"
    readme_path.write_text(GH_PAGES_README, encoding="utf-8")
    return readme_path


def commit_changes(worktree_path: Path, use_datalad: bool = True) -> bool:
    """Commit changes, optionally using datalad.

    Args:
        worktree_path: Path to the worktree.
        use_datalad: Whether to use datalad if available.

    Returns:
        True if there were changes to commit.
    """
    # Check if there are changes
    result = run_cmd(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        capture=True,
    )
    if not result.stdout.strip():
        return False

    # Add all files
    run_cmd(["git", "add", "-A"], cwd=worktree_path)

    if use_datalad and has_datalad():
        run_cmd(
            ["datalad", "save", "-m", "Update demo website"],
            cwd=worktree_path,
        )
    else:
        run_cmd(
            ["git", "commit", "-m", "Update demo website\n\nGenerated by mykrok gh-pages"],
            cwd=worktree_path,
        )

    return True


def check_log_only_changes(worktree_path: Path) -> bool:
    """Check if the only changes in HEAD commit are log files.

    Args:
        worktree_path: Path to the worktree.

    Returns:
        True if only log files changed (should reset).
    """
    result = run_cmd(
        ["git", "diff", "--name-only", "HEAD^..HEAD"],
        cwd=worktree_path,
        capture=True,
        check=False,
    )

    if result.returncode != 0:
        # No parent commit (first commit)
        return False

    changed_files = result.stdout.strip().split("\n")
    if not changed_files or changed_files == [""]:
        return False

    return all(f.endswith(".log") for f in changed_files)


def cleanup_worktree(repo_root: Path, worktree_path: Path) -> None:
    """Remove the worktree.

    Args:
        repo_root: Path to the git repository root.
        worktree_path: Path to the worktree.
    """
    if worktree_path.exists():
        run_cmd(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=repo_root,
            check=False,
        )


def generate_gh_pages(
    repo_root: Path,
    worktree_path: Path | None = None,
    push: bool = False,
    use_datalad: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate GitHub Pages demo website.

    Args:
        repo_root: Path to the git repository root.
        worktree_path: Path for gh-pages worktree (default: repo_root/.gh-pages).
        push: Whether to push to origin after committing.
        use_datalad: Whether to use datalad if available.
        seed: Random seed for reproducible demo data.

    Returns:
        Dictionary with results.

    Raises:
        subprocess.CalledProcessError: If a git command fails.
        RuntimeError: If not in a git repository.
    """
    if not (repo_root / ".git").exists():
        raise RuntimeError("Not in a git repository")

    if worktree_path is None:
        worktree_path = repo_root / ".gh-pages"

    worktree_path = worktree_path.resolve()

    results: dict[str, Any] = {
        "worktree_path": str(worktree_path),
        "branch": "gh-pages",
        "is_new_branch": False,
        "had_changes": False,
        "pushed": False,
        "reset_log_only": False,
    }

    try:
        # Setup worktree
        is_new_branch = setup_worktree(repo_root, worktree_path)
        results["is_new_branch"] = is_new_branch

        # Clean existing content
        clean_worktree(worktree_path)

        # Initialize as DataLad dataset if new and datalad available
        if is_new_branch and use_datalad and has_datalad():
            run_cmd(["datalad", "create", "--force", "."], cwd=worktree_path)

        # Generate demo data directly in worktree (no data/ subfolder)
        generate_demo_data(worktree_path, seed=seed)

        # Generate HTML
        generate_html(worktree_path)

        # Create README
        create_readme(worktree_path)

        # Commit changes
        had_changes = commit_changes(worktree_path, use_datalad=use_datalad)
        results["had_changes"] = had_changes

        # Check if only log files changed
        if had_changes and check_log_only_changes(worktree_path):
            run_cmd(["git", "reset", "--hard", "HEAD^"], cwd=worktree_path)
            results["had_changes"] = False
            results["reset_log_only"] = True

        # Push if requested
        if push and results["had_changes"]:
            run_cmd(["git", "push", "-u", "origin", "gh-pages"], cwd=worktree_path)
            results["pushed"] = True

        return results

    finally:
        # Always try to clean up worktree
        cleanup_worktree(repo_root, worktree_path)


def get_expected_files() -> list[str]:
    """Get list of files expected in gh-pages branch.

    Returns:
        List of expected file paths (relative to worktree root).
    """
    return [
        "index.html",
        "README.md",
        "athletes.tsv",
        "assets/leaflet/leaflet.js",
        "assets/leaflet/leaflet.css",
        "assets/hyparquet/index.js",
        "athl=alice/sessions.tsv",
        "athl=bob/sessions.tsv",
    ]


def verify_gh_pages_content(worktree_path: Path) -> dict[str, Any]:
    """Verify gh-pages content has all expected files.

    Args:
        worktree_path: Path to the worktree.

    Returns:
        Dictionary with verification results.
    """
    expected = get_expected_files()
    missing = []
    present = []

    for filepath in expected:
        full_path = worktree_path / filepath
        if full_path.exists():
            present.append(filepath)
        else:
            missing.append(filepath)

    return {
        "expected": expected,
        "present": present,
        "missing": missing,
        "complete": len(missing) == 0,
    }
