"""Tests for the pytest gate added to _pycompile."""

import textwrap
from pathlib import Path

import pytest

from shepherd_mcp.compile import run as compile_run


def _make_python_project(tmp_path: Path, src: str = "", test_src: str | None = None) -> Path:
    """
    Create a minimal Python project in tmp_path.
    Writes pyproject.toml so the compile gate detects it as a Python project.
    Optionally writes tests/test_something.py.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\nversion = '0.1'\n")
    (tmp_path / "mymodule.py").write_text(src or "# empty\n")
    if test_src is not None:
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_mymodule.py").write_text(test_src)
    return tmp_path


def test_no_tests_dir_skips_pytest(tmp_path):
    """When there is no tests/ directory, pytest should not run and result is success."""
    proj = _make_python_project(tmp_path, src="x = 1\n")
    result = compile_run(str(proj))
    assert result.success
    assert "pytest" not in result.output.lower()


def test_passing_tests_return_success(tmp_path):
    """When tests/ exists and all tests pass, result is success."""
    proj = _make_python_project(
        tmp_path,
        src="def add(a, b):\n    return a + b\n",
        test_src="from mymodule import add\ndef test_add():\n    assert add(1, 2) == 3\n",
    )
    result = compile_run(str(proj))
    assert result.success
    assert "pytest" in result.output.lower()


def test_failing_tests_return_failure(tmp_path):
    """When tests/ exists and a test fails, result is failure."""
    proj = _make_python_project(
        tmp_path,
        src="def add(a, b):\n    return a - b  # deliberately wrong\n",
        test_src="from mymodule import add\ndef test_add():\n    assert add(1, 2) == 3\n",
    )
    result = compile_run(str(proj))
    assert not result.success
    assert "pytest" in result.output.lower() or "assert" in result.output.lower()


def test_conftest_triggers_pytest(tmp_path):
    """A conftest.py at root (no tests/ dir) should also trigger pytest."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\nversion = '0.1'\n")
    (tmp_path / "mymodule.py").write_text("x = 1\n")
    (tmp_path / "conftest.py").write_text("# conftest\n")
    result = compile_run(str(proj := tmp_path))
    assert result.success
    assert "pytest" in result.output.lower()


def test_pyflakes_failure_skips_pytest(tmp_path):
    """If pyflakes fails, pytest should not run."""
    proj = _make_python_project(
        tmp_path,
        src="import os\nx = undefined_name\n",  # pyflakes will flag undefined_name
        test_src="def test_dummy(): pass\n",
    )
    result = compile_run(str(proj))
    assert not result.success
    # Should fail on pyflakes, not get to pytest
    assert "undefined" in result.output or "pyflakes" in result.output.lower() or "undefined_name" in result.output
