"""Subprocess wrapper.

Replaces the legacy NamedTemporaryFile + Popen pattern with a single call to
`subprocess.run`. Encoding is fixed to UTF-8 with `errors="replace"` so a
non-UTF-8 byte in a compiler error message no longer crashes decoding.

The function never raises on a non-zero return code — callers (build dispatch,
status.summarize) decide how to react. Missing executables surface as a
negative return code with the diagnostic message in stderr, so callers see a
real signal rather than an exception.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str
    took: float


def run(
    cmd: Sequence[str] | str,
    *,
    cwd: Path | str | None = None,
    shell: bool = False,
) -> RunResult:
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd is not None else None,
            shell=shell,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        rc = completed.returncode
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except FileNotFoundError as exc:
        _logger.warning("executable not found: %s", exc)
        rc = -1
        stdout = ""
        stderr = f"executable not found: {exc}"
    took = round(time.perf_counter() - start, 3)
    return RunResult(returncode=rc, stdout=stdout, stderr=stderr, took=took)
