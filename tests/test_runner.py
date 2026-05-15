"""Tests for te_builder.runner.

The legacy implementation captured stdout/stderr by handing
`NamedTemporaryFile` objects to `subprocess.Popen` (Py2 era workaround for
encoding limits). The replacement is `subprocess.run` with text capture and
UTF-8 + replace error handling, plus a deterministic shape — return code,
stdout, stderr, elapsed seconds.
"""

from __future__ import annotations

import sys
from pathlib import Path

from te_builder.runner import RunResult, run


def test_run_returns_runresult_with_returncode_stdout_stderr() -> None:
    script = "print('hi'); import sys; sys.stderr.write('err')"
    result = run([sys.executable, "-c", script])
    assert isinstance(result, RunResult)
    assert result.returncode == 0
    assert "hi" in result.stdout
    assert "err" in result.stderr
    assert result.took >= 0


def test_run_nonzero_returncode_does_not_raise() -> None:
    result = run([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.returncode == 3


def test_run_decodes_utf8_with_replacement_errors() -> None:
    """Writing raw bytes that are not valid UTF-8 must not crash decoding."""
    script = "import sys; sys.stdout.buffer.write(b'\\xff\\xfe')"
    result = run([sys.executable, "-c", script])
    assert result.returncode == 0
    assert result.stdout  # decoded with replacement marker, non-empty


def test_run_respects_cwd(tmp_path: Path) -> None:
    target = tmp_path / "where_am_i"
    target.mkdir()
    result = run([sys.executable, "-c", "import os; print(os.getcwd())"], cwd=target)
    assert str(target.resolve()).lower() in result.stdout.lower()


def test_run_missing_executable_returns_negative_one() -> None:
    """No silent fallback: a missing executable surfaces as rc != 0."""
    result = run(["__definitely_not_a_real_binary_xyz__"])
    assert result.returncode != 0
    assert result.stderr  # diagnostic message present
