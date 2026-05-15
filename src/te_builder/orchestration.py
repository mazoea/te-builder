"""Build orchestration helpers used by the CLI loop.

te-external solution files emit configuration-suffixed artifact names
(e.g. zlib-debug-mtdll-x64.lib vs zlib-release-mtdll-x64.lib), so Debug
and Release outputs already coexist safely in a single flat libs/ dir.
Downstream consumers (libpng, freetype, ...) reference dependencies via
flat libs/<dep>/<name>.lib paths through junctions, so the flat layout
is the contract te-builder must preserve — without it those consumers
fail to link unless te-builder is re-run.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from .config import ProjectDefaults

_logger = logging.getLogger(__name__)


def project_lib_dir(project_dir: Path, defaults: ProjectDefaults) -> Path:
    return project_dir / defaults.output_libs


def copy_libs_for_configuration(
    project_dir: Path, configuration: str, defaults: ProjectDefaults
) -> None:
    del configuration  # output filenames already encode the configuration
    output_dir = project_lib_dir(project_dir, defaults)
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in defaults.copy:
        for source in project_dir.glob(pattern):
            if not source.is_file():
                continue
            target = output_dir / source.name
            _logger.debug("copy %s -> %s", source, target)
            shutil.copy(str(source), str(target))


def prepare_log_file(log_file: Path) -> None:
    """Ensure the parent directory exists and the log file does not.

    Each MSBuild file logger appends to its target, so a stale log from a
    previous run would otherwise leak into `summarize_from_log()`. The
    test that pins this behaviour writes "0 Error(s)" then asserts the
    summary of a failed build reflects the real return code rather than
    the stale content.
    """
    log_file.parent.mkdir(parents=True, exist_ok=True)
    if log_file.exists():
        log_file.unlink()


def retry_build(attempt: Callable[[], int], *, max_retries: int) -> int:
    """Run `attempt` once, then up to `max_retries` more times until it
    returns 0. Returns the last return code observed. Fixes the legacy bug
    where every retry's return code was summed into the global rc."""
    last = attempt()
    if last == 0:
        return 0
    for _ in range(max_retries):
        last = attempt()
        if last == 0:
            return 0
    return last
