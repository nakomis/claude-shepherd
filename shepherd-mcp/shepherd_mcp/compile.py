"""Compile gate — runs type-checking / build in the worktree to catch errors cheaply."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CompileResult:
    success: bool
    output: str   # combined stdout + stderr


def run(worktree_path: str) -> CompileResult:
    """
    Detect the project type and run the appropriate compile check.

    TypeScript (CDK/Node): tsc --noEmit
    Vite frontend:         vite build (or tsc -b if no vite.config)
    Python:                py_compile check (basic syntax only)

    Falls back to a no-op success if no recognised project type is detected.
    """
    root = Path(worktree_path)

    if (root / "tsconfig.json").exists():
        return _tsc(worktree_path)

    if (root / "pyproject.toml").exists() or (root / "setup.py").exists():
        return _pycompile(worktree_path)

    return CompileResult(success=True, output="No recognised project type — compile gate skipped.")


def _tsc(worktree_path: str) -> CompileResult:
    result = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    return CompileResult(success=result.returncode == 0, output=output)


def _pycompile(worktree_path: str) -> CompileResult:
    py_files = list(Path(worktree_path).rglob("*.py"))
    errors = []
    for f in py_files:
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(f)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            errors.append(f"{f.name}: {result.stderr.strip()}")

    if errors:
        return CompileResult(success=False, output="\n".join(errors))
    return CompileResult(success=True, output=f"Syntax OK ({len(py_files)} files checked)")
