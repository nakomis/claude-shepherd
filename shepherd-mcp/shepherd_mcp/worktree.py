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


def write_and_commit(worktree_path: str, files: dict[str, str], message: str) -> None:
    """Write files into the worktree and commit them."""
    root = Path(worktree_path)
    for rel_path, content in files.items():
        target = root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _run(["git", "add", "-A"], cwd=worktree_path)
    _run(["git", "commit", "-m", message], cwd=worktree_path)


def apply_patches(worktree_path: str, patches: list[str]) -> None:
    """Apply a list of unified diff patches to the worktree via `git apply`."""
    import tempfile, os
    for patch_text in patches:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".patch",
                                        delete=False, encoding="utf-8") as f:
            f.write(patch_text)
            tmp = f.name
        try:
            # --3way: fall back to three-way merge when hunk offsets are wrong
            # --ignore-whitespace: tolerate whitespace drift
            _run(["git", "apply", "--3way", "--ignore-whitespace", "--index", tmp],
                 cwd=worktree_path)
        finally:
            os.unlink(tmp)


def _run(cmd: list[str], cwd: str) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command {cmd} failed:\n{result.stderr}")
    return result
