"""Tests for the build-orchestration helpers.

Two legacy bugs are pinned here:
- `copy_libs` wrote all configurations into one `libs/` directory, so a
  later configuration silently overwrote an earlier one. We now namespace
  by configuration.
- The retry loop summed return codes from every attempt and never broke
  on a successful retry. We break on the first success.
"""

from __future__ import annotations

from pathlib import Path

from te_builder.config import ProjectDefaults
from te_builder.orchestration import (
    cleanup_libs_for_configuration,
    copy_libs_for_configuration,
    retry_build,
)


def _fake_project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "fake-lib"
    output = project_dir / "projects" / "output"
    output.mkdir(parents=True)
    (output / "fake.lib").write_text("a", encoding="utf-8")
    (output / "fake.dll").write_text("b", encoding="utf-8")
    return project_dir


def test_copy_libs_namespaces_by_configuration(tmp_path: Path) -> None:
    project_dir = _fake_project(tmp_path)
    defaults = ProjectDefaults()
    copy_libs_for_configuration(project_dir, "Release|x64", defaults)
    copied = sorted((project_dir / "libs" / "Release-x64").iterdir())
    assert [path.name for path in copied] == ["fake.dll", "fake.lib"]


def test_copy_libs_two_configurations_do_not_collide(tmp_path: Path) -> None:
    project_dir = _fake_project(tmp_path)
    defaults = ProjectDefaults()
    copy_libs_for_configuration(project_dir, "Release|x64", defaults)
    # rebuild produces new artifacts in the same output dir
    (project_dir / "projects" / "output" / "fake.dll").write_text(
        "debug", encoding="utf-8"
    )
    copy_libs_for_configuration(project_dir, "Debug-MTDLL|x64", defaults)
    release_dll = (project_dir / "libs" / "Release-x64" / "fake.dll").read_text()
    debug_dll = (project_dir / "libs" / "Debug-MTDLL-x64" / "fake.dll").read_text()
    assert release_dll == "b"
    assert debug_dll == "debug"


def test_cleanup_libs_scoped_to_configuration(tmp_path: Path) -> None:
    project_dir = _fake_project(tmp_path)
    defaults = ProjectDefaults()
    copy_libs_for_configuration(project_dir, "Release|x64", defaults)
    copy_libs_for_configuration(project_dir, "Debug-MTDLL|x64", defaults)
    cleanup_libs_for_configuration(project_dir, "Release|x64", defaults)
    assert not (project_dir / "libs" / "Release-x64" / "fake.lib").exists()
    assert (project_dir / "libs" / "Debug-MTDLL-x64" / "fake.lib").exists()


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


def test_retry_build_returns_last_nonzero_when_all_fail() -> None:
    attempts: list[int] = []

    def attempt() -> int:
        attempts.append(len(attempts))
        return 5

    rc = retry_build(attempt, max_retries=3)
    assert rc == 5
    assert len(attempts) == 4  # initial + 3 retries
