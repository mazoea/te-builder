"""Detect installed Visual Studio versions and pick a toolset.

Wraps Microsoft's `vswhere.exe` (shipped with the VS Installer) to discover
local installations. Each install is mapped to its MSVC platform toolset:

    VS 2017 (15.x) -> v141
    VS 2019 (16.x) -> v142
    VS 2022 (17.x) -> v143
    VS 2026 (18.x) -> v145   (v144 is intentionally skipped by Microsoft)

`select_toolset()` is the single decision point the CLI calls. It is
non-interactive by default; the caller (cli.main) decides whether the
session is a TTY and only then sets `interactive=True`. CI pipelines that
do not pass `--msvc-toolset` therefore get the highest detected toolset
without blocking on a prompt.

Two CLI modes share the same detection pipeline:

- `python -m te_builder.vs_detect` (no flag) prints a one-line summary per
  install — wired into `scripts/list-vs.bat`.
- `python -m te_builder.vs_detect --toolset` prints only the selected
  toolset short name to stdout (exit 0) or nothing on stdout (exit 1) if
  no install is detected. Sibling repos (te-external-leptonica's
  `cmaker.bat`) shell out to this mode and apply their own fallback when
  the script is unavailable.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_logger = logging.getLogger(__name__)

_TOOLSET_BY_MAJOR: dict[str, str] = {
    "15": "v141",
    "16": "v142",
    "17": "v143",
    "18": "v145",
}


@dataclass(frozen=True)
class VsInstall:
    display_name: str
    installation_path: Path
    installation_version: str
    toolset: str


def toolset_for_version(installation_version: str) -> str | None:
    if not installation_version:
        return None
    major = installation_version.split(".", 1)[0]
    return _TOOLSET_BY_MAJOR.get(major)


def parse_vswhere_output(raw: str) -> list[VsInstall]:
    if not raw.strip():
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        _logger.warning("could not parse vswhere output: %s", exc)
        return []
    installs: list[VsInstall] = []
    for entry in entries:
        version = str(entry.get("installationVersion", ""))
        toolset = toolset_for_version(version)
        if toolset is None:
            continue
        installs.append(
            VsInstall(
                display_name=str(entry.get("displayName", "Visual Studio")),
                installation_path=Path(str(entry.get("installationPath", ""))),
                installation_version=version,
                toolset=toolset,
            )
        )
    return installs


def _default_vswhere_path() -> Path:
    # os.environ is case-insensitive on Windows where this code is meaningful;
    # use the upper-case form so ruff's SIM112 stays happy on Linux too.
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
    return (
        Path(program_files_x86) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    )


def detect_installs(vswhere: Path | None = None) -> list[VsInstall]:
    """Run vswhere and return parsed VsInstall records. Returns [] on any
    failure (missing vswhere, non-Windows host, malformed output)."""
    vswhere_path = vswhere or _default_vswhere_path()
    if not vswhere_path.is_file():
        _logger.debug("vswhere not found at %s", vswhere_path)
        return []
    try:
        completed = subprocess.run(
            [
                str(vswhere_path),
                "-products",
                "*",
                "-format",
                "json",
                "-utf8",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        _logger.warning("could not run %s: %s", vswhere_path, exc)
        return []
    if completed.returncode != 0:
        _logger.warning(
            "vswhere exited with rc=%d: %s",
            completed.returncode,
            completed.stderr.strip(),
        )
        return []
    return parse_vswhere_output(completed.stdout)


def _ranked(installs: list[VsInstall]) -> list[VsInstall]:
    return sorted(installs, key=lambda inst: inst.installation_version, reverse=True)


def select_toolset(
    installs: list[VsInstall],
    *,
    interactive: bool,
    prompt: Callable[[str], str] = input,
) -> str | None:
    if not installs:
        return None
    ranked = _ranked(installs)
    if len(ranked) == 1 or not interactive:
        return ranked[0].toolset
    sys.stderr.write("Multiple Visual Studio installations detected:\n")
    for index, install in enumerate(ranked, start=1):
        sys.stderr.write(
            f"  {index}. {install.display_name}  "
            f"[{install.installation_version} -> {install.toolset}]\n"
        )
    while True:
        raw = prompt(f"Select [1-{len(ranked)}, default 1]: ").strip()
        if not raw:
            return ranked[0].toolset
        try:
            choice = int(raw)
        except ValueError:
            sys.stderr.write("Not a number; try again.\n")
            continue
        if 1 <= choice <= len(ranked):
            return ranked[choice - 1].toolset
        sys.stderr.write(f"Out of range; choose 1..{len(ranked)}.\n")


def _format_install(install: VsInstall) -> str:
    return (
        f"{install.display_name:<40} "
        f"version={install.installation_version}  "
        f"toolset={install.toolset}  "
        f"path={install.installation_path}"
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="te_builder.vs_detect",
        description="List Visual Studio installs (default) or print the "
        "selected MSVC platform toolset short name (--toolset).",
    )
    parser.add_argument(
        "--toolset",
        action="store_true",
        help="Print only the highest-detected toolset short name (e.g. "
        "v145) to stdout and exit 0; exit 1 with empty stdout if no "
        "install is found, so shell callers can apply their own fallback.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry for `python -m te_builder.vs_detect`.

    Default mode lists installs (used by scripts/list-vs.bat). `--toolset`
    is the machine-readable mode consumed by sibling repos' build scripts.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname).4s %(message)s")
    args = _build_arg_parser().parse_args(argv)
    installs = detect_installs()
    if args.toolset:
        chosen = select_toolset(installs, interactive=False)
        if chosen is None:
            return 1
        sys.stdout.write(chosen + "\n")
        sys.stdout.flush()
        return 0
    if not installs:
        sys.stderr.write(
            "No Visual Studio installations detected. "
            "Install vswhere with Visual Studio Installer, or pass "
            "--msvc-toolset vXXX to bypass detection.\n"
        )
        return 1
    for install in _ranked(installs):
        sys.stdout.write(_format_install(install) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
