"""Tests for the build-orchestration helpers.

Legacy bugs pinned here:
- The retry loop summed return codes from every attempt and never broke
  on a successful retry. We break on the first success.
- prepare_log_file must wipe stale logs so summarize_from_log() never
  reports a previous run's "0 Error(s)" against a failed build.

Layout note: copy_libs_for_configuration writes to a flat libs/ dir.
te-external solution files emit configuration-suffixed filenames
(e.g. zlib-debug-mtdll-x64.lib), so Debug and Release artifacts coexist
without collision, and downstream consumers (libpng, freetype) can link
against libs/*.lib through junctions without depending on te-builder
to mirror files into a per-configuration subdir.
"""

from __future__ import annotations

from pathlib import Path

from te_builder.config import ProjectDefaults
from te_builder.orchestration import (
    copy_libs_for_configuration,
    prepare_log_file,
    retry_build,
)


def _fake_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "fake-lib"
    output = project_dir / "projects" / "output"
    output.mkdir(parents=True)
    (output / "fake-release-mtdll-x64.lib").write_text("a", encoding="utf-8")
    (output / "fake-release-mtdll-x64.dll").write_text("b", encoding="utf-8")
    return project_dir


def test_copy_libs_writes_flat(tmp_path: Path) -> None:
    project_dir = _fake_project(tmp_path)
    defaults = ProjectDefaults()
    copy_libs_for_configuration(project_dir, "Release-MTDLL|x64", defaults)
    copied = sorted((project_dir / "libs").glob("*"))
    assert [path.name for path in copied] == [
        "fake-release-mtdll-x64.dll",
        "fake-release-mtdll-x64.lib",
    ]


def test_copy_libs_both_configurations_coexist(tmp_path: Path) -> None:
    """Configuration-suffixed filenames let Debug and Release coexist in
    the flat libs/ dir without overwriting each other."""
    project_dir = tmp_path / "fake-lib"
    output = project_dir / "projects" / "output"
    output.mkdir(parents=True)
    (output / "fake-release-mtdll-x64.lib").write_text("rel", encoding="utf-8")
    defaults = ProjectDefaults()
    copy_libs_for_configuration(project_dir, "Release-MTDLL|x64", defaults)

    (output / "fake-debug-mtdll-x64.lib").write_text("dbg", encoding="utf-8")
    copy_libs_for_configuration(project_dir, "Debug-MTDLL|x64", defaults)

    libs = project_dir / "libs"
    assert (libs / "fake-release-mtdll-x64.lib").read_text() == "rel"
    assert (libs / "fake-debug-mtdll-x64.lib").read_text() == "dbg"


def test_retry_build_breaks_on_first_success() -> None:
    """Regression: legacy retry kept running even after a success and
    accumulated return codes. Now the first 0 wins, no extra attempts."""
    attempts: list[int] = []

    def attempt() -> int:
        attempts.append(len(attempts))
        return 0 if len(attempts) == 1 else 99  # first call succeeds

    rc = retry_build(attempt, max_retries=3)
    assert rc == 0
    assert len(attempts) == 1


def test_prepare_log_file_removes_existing_log(tmp_path: Path) -> None:
    """Stale log files from previous builds must be removed so that
    summarize_from_log() never reads pre-existing content into the row
    when the current build failed (or never ran)."""
    log_dir = tmp_path / "_logs"
    log_dir.mkdir()
    stale = log_dir / "zlib.Release-MTDLL-x64.log"
    stale.write_text("0 Error(s)\n", encoding="utf-8")
    prepare_log_file(stale)
    assert not stale.exists()


def test_prepare_log_file_creates_parent_dir(tmp_path: Path) -> None:
    log = tmp_path / "deep" / "nested" / "zlib.log"
    prepare_log_file(log)
    assert log.parent.is_dir()
    assert not log.exists()


def test_retry_build_returns_last_nonzero_when_all_fail() -> None:
    attempts: list[int] = []

    def attempt() -> int:
        attempts.append(len(attempts))
        return 5

    rc = retry_build(attempt, max_retries=3)
    assert rc == 5
    assert len(attempts) == 4  # initial + 3 retries
