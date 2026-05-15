"""MSBuild integration.

Centralises .sln discovery and configuration validation. The legacy code
opened the .sln file without a context manager (handle leak on Windows),
assumed the SolutionConfigurationPlatforms section existed, and reacted to
a missing solution with `assert sln_file is not None` — which kills the
whole orchestrator with a stack trace. None of that is true here.
"""

from __future__ import annotations

import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

_MAGIC = "SolutionConfigurationPlatforms"
_END = "EndGlobalSection"


def discover_sln(
    project_dir: Path, solution_path: str, solution_glob: str
) -> Path | None:
    sln_dir = project_dir / solution_path
    candidates = sorted(sln_dir.glob(solution_glob))
    if not candidates:
        return None
    if len(candidates) > 1:
        preferred = [path for path in candidates if path.name.endswith("project.sln")]
        if len(preferred) == 1:
            return preferred[0]
    return candidates[0] if len(candidates) == 1 else None


def validate_configuration(sln_path: Path, configuration: str) -> bool:
    """Return True if `configuration` (e.g. `Release|x64`) is declared in
    the SolutionConfigurationPlatforms section. Returns False on missing
    section or unreadable file rather than raising — the caller decides
    how to report it."""
    try:
        with sln_path.open("r", encoding="utf-8", errors="replace") as handle:
            in_section = False
            available: list[str] = []
            for raw_line in handle:
                line = raw_line.strip()
                if not in_section and _MAGIC in line:
                    in_section = True
                    continue
                if in_section and _END in line:
                    break
                if in_section and "=" in line:
                    available.append(line.split("=", 1)[1].strip())
    except OSError as exc:
        _logger.warning("could not read %s: %s", sln_path, exc)
        return False
    return configuration in available
