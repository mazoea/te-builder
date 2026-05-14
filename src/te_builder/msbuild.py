"""MSBuild integration.

Centralises solution discovery and configuration validation. Two solution
formats are in play: the legacy `.sln` text format the hand-curated
te-external image libraries ship, and the `.slnx` XML format CMake + VS
2022/2026 generate for the leptonica / tesseract projects. Both are
discovered and validated here.

The legacy code opened the .sln file without a context manager (handle leak
on Windows), assumed the SolutionConfigurationPlatforms section existed, and
reacted to a missing solution with `assert sln_file is not None` — which
kills the whole orchestrator with a stack trace. None of that is true here.
"""

from __future__ import annotations

import logging
from pathlib import Path
from xml.etree import ElementTree

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
    if len(candidates) == 1:
        return candidates[0]
    # Multiple matches: the hand-curated te-external solution is always named
    # project.sln (CMake projects emit a single uniquely-named .slnx, so they
    # never reach here). Anything else is ambiguous — let the caller report
    # NO SOLUTION rather than guessing.
    preferred = [path for path in candidates if path.stem == "project"]
    return preferred[0] if len(preferred) == 1 else None


def _configurations_from_sln(sln_path: Path) -> list[str]:
    """Parse the legacy `.sln` text format. The SolutionConfigurationPlatforms
    section lists `Config|Platform` entries verbatim."""
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
    return available


def _configurations_from_slnx(sln_path: Path) -> list[str]:
    """Parse the modern `.slnx` XML format. The <Configurations> element lists
    <BuildType> and <Platform> children separately; the solution
    configurations are their cross product, e.g. `RelWithDebInfo|x64`."""
    configs = ElementTree.parse(sln_path).getroot().find("Configurations")
    if configs is None:
        return []
    build_types = [e.get("Name") for e in configs.findall("BuildType")]
    platforms = [e.get("Name") for e in configs.findall("Platform")]
    return [
        f"{build_type}|{platform}"
        for build_type in build_types
        if build_type
        for platform in platforms
        if platform
    ]


def validate_configuration(sln_path: Path, configuration: str) -> bool:
    """Return True if `configuration` (e.g. `Release|x64`) is declared in the
    solution. Returns False on a missing section, malformed XML, or an
    unreadable file rather than raising — the caller decides how to report it.
    """
    try:
        if sln_path.suffix.lower() == ".slnx":
            available = _configurations_from_slnx(sln_path)
        else:
            available = _configurations_from_sln(sln_path)
    except (OSError, ElementTree.ParseError) as exc:
        _logger.warning("could not read %s: %s", sln_path, exc)
        return False
    return configuration in available
