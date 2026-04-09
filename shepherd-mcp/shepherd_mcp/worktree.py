"""Git worktree management for isolated drone job execution."""

import subprocess
from pathlib import Path


def create(project_path: str, branch: str) -> str:
    """
    Create a git worktree for a drone job.

    Returns the worktree path.
    """
    repo = Path(project_path)
    worktree_path = repo.parent / f".shepherd-worktrees/{branch}"
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    _run(["git", "worktree", "add", "-b", branch, str(worktree_path)], cwd=project_path)
    return str(worktree_path)


def remove(project_path: str, worktree_path: str) -> None:
    """Remove a git worktree and delete its branch."""
    _run(["git", "worktree", "remove", "--force", worktree_path], cwd=project_path)


def merge(project_path: str, branch: str, worktree_path: str) -> None:
    """
    Merge the worktree branch into the current branch of the main working tree.
    Uses --no-ff so the merge is always a merge commit.
    """
    _run(["git", "merge", "--no-ff", branch], cwd=project_path)
    remove(project_path, worktree_path)
    _run(["git", "branch", "-d", branch], cwd=project_path)


def write_files(worktree_path: str, files: dict[str, str]) -> None:
    """Write a dict of {relative_path: content} into the worktree."""
    root = Path(worktree_path)
    for rel_path, content in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command {cmd} failed:\n{result.stderr}")
    return result
