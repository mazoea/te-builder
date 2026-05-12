"""Build status formatting.

`summarize()` is the only place the package decides "did this build pass".
The decision is driven by the subprocess return code (locale-independent);
the English `N Error(s)` regex is used only to enrich the human-readable
line. Legacy behaviour scraped the regex *as the decision* and silently
passed on non-English Windows installs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

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
