"""Build orchestration helpers used by the CLI loop.

The legacy code mixed three responsibilities in one block: cleaning up the
previous configuration's output, dispatching to MSBuild or cmake, and
copying the result back into a shared `libs/` directory. The shared dir
made it impossible to keep both Release and Debug-MTDLL outputs around at
the same time. We now namespace by configuration.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from pathlib import Path

from .config import ProjectDefaults

_logger = logging.getLogger(__name__)


def _configuration_dir_name(configuration: str) -> str:
    """`Release|x64` is not a legal directory name on Windows. We replace
    the pipe with a dash, matching the log-file naming used elsewhere."""
    return configuration.replace("|", "-")


def configuration_lib_dir(
    project_dir: Path, configuration: str, defaults: ProjectDefaults
) -> Path:
    return project_dir / defaults.output_libs / _configuration_dir_name(configuration)


def copy_libs_for_configuration(
    project_dir: Path, configuration: str, defaults: ProjectDefaults
) -> None:
    output_dir = configuration_lib_dir(project_dir, configuration, defaults)
    output_dir.mkdir(parents=True, exist_ok=True)
    for pattern in defaults.copy:
        for source in project_dir.glob(pattern):
            if not source.is_file():
                continue
            target = output_dir / source.name
            _logger.debug("copy %s -> %s", source, target)
            shutil.copy(str(source), str(target))


def cleanup_libs_for_configuration(
    project_dir: Path, configuration: str, defaults: ProjectDefaults
) -> None:
    output_dir = configuration_lib_dir(project_dir, configuration, defaults)
    if not output_dir.exists():
        return
    for entry in list(output_dir.iterdir()):
        if entry.is_file():
            _logger.debug("remove %s", entry)
            entry.unlink()


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
