"""Build status formatting.

`summarize()` produces the human-readable status row given a return code
and the captured stdout/log contents. The ok/failed decision is driven by
the return code (locale-independent); the English `N Error(s)` regex is
used only to enrich the line. Legacy behaviour scraped the regex *as the
decision* and silently passed on non-English Windows installs.

`summarize_from_log()` is a thin wrapper that reads MSBuild's file logger
output before calling `summarize()`. The CLI invokes it after each build
to keep status formatting consistent across MSBuild and cmake paths.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ERROR_LINE = re.compile(r"(\d+)\s+Error\(s\)")


@dataclass(frozen=True)
class StatusRow:
    ok: bool
    line: str


def _extract_error_line(stdout: str) -> str | None:
    for line in reversed(stdout.splitlines()):
        if _ERROR_LINE.search(line):
            return line.strip()
    return None


def summarize(
    *,
    returncode: int,
    stdout: str,
    project_name: str,
    configuration: str,
) -> StatusRow:
    ok = returncode == 0
    parsed = _extract_error_line(stdout)
    if parsed is None:
        tail = "OK" if ok else f"FAILED (rc={returncode}) !!!!!!!!!!"
    else:
        match = _ERROR_LINE.search(parsed)
        count = int(match.group(1)) if match else 0
        marker = " !!!!!!!!!!" if count > 0 or not ok else ""
        tail = f"{parsed}{marker}"
    return StatusRow(ok=ok, line=f"{project_name:>15} : {configuration:>20} : {tail:>15}")


def summarize_from_log(
    *,
    returncode: int,
    log_file: Path,
    project_name: str,
    configuration: str,
) -> StatusRow:
    """Read `log_file` (the MSBuild file logger output) and call
    `summarize()`. Missing or unreadable log files degrade gracefully:
    the row still reflects `returncode` accurately, but the line lacks
    the "N Error(s)" tail."""
    try:
        stdout = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stdout = ""
    return summarize(
        returncode=returncode,
        stdout=stdout,
        project_name=project_name,
        configuration=configuration,
    )
