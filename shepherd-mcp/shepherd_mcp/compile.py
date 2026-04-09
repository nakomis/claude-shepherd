"""Compile gate — runs type-checking / build in the worktree to catch errors cheaply."""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CompileResult:
    success: bool
    output: str   # combined stdout + stderr


def run(worktree_path: str) -> CompileResult:
    """
    Detect the project type and run the appropriate compile check.
    Searches the root and common subdirectories for project files.

    TypeScript: tsc --noEmit (run in each directory containing a tsconfig.json)
    Python:     pyflakes across all .py files (catches undefined names, bad imports, wrong APIs)
    """
    root = Path(worktree_path)

    # Find all tsconfig.json files, excluding node_modules
    tsconfigs = [
        p.parent for p in root.rglob("tsconfig.json")
        if "node_modules" not in p.parts
    ]
    if tsconfigs:
        results = [_tsc(str(d)) for d in tsconfigs]
        failures = [r for r in results if not r.success]
        if failures:
            return CompileResult(success=False, output="\n\n".join(r.output for r in failures))
        outputs = "\n".join(f"{d.relative_to(root)}: OK" for d in tsconfigs)
        return CompileResult(success=True, output=outputs)

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
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", worktree_path],
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        return CompileResult(success=False, output=output)

    # Run pytest if a tests/ directory or conftest.py is present
    root = Path(worktree_path)
    if (root / "tests").is_dir() or (root / "conftest.py").exists():
        env = {**os.environ, "PYTHONPATH": worktree_path}
        pytest_result = subprocess.run(
            [sys.executable, "-m", "pytest", worktree_path, "--tb=short", "-q", "--no-header"],
            capture_output=True,
            text=True,
            env=env,
        )
        pytest_output = (pytest_result.stdout + pytest_result.stderr).strip()
        # Exit code 5 = no tests collected — treat as success
        if pytest_result.returncode not in (0, 5):
            return CompileResult(success=False, output=pytest_output)
        return CompileResult(success=True, output=f"{output or 'pyflakes: OK'}\npytest: OK")

    return CompileResult(success=True, output=output or "pyflakes: OK")
