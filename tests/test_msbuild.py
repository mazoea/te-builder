"""Tests for te_builder.msbuild.

Pins three legacy bugs:
- the original `validate_configuration` opened the .sln without `with`,
  leaking the handle when a parse error occurred;
- it assumed the magic section existed and would loop forever on malformed
  files;
- `assert sln_file is not None` killed the whole run with a stack trace
  instead of recording one missing-solution row in the status table.

Also covers the modern `.slnx` XML solution format that CMake + VS 2022/2026
generate for the leptonica / tesseract projects.
"""

from __future__ import annotations

from pathlib import Path

from te_builder.msbuild import discover_sln, validate_configuration

FIXTURES = Path(__file__).parent / "fixtures"


def test_validate_configuration_finds_listed_configuration() -> None:
    assert validate_configuration(FIXTURES / "minimal.sln", "Release|x64") is True


def test_validate_configuration_rejects_missing_configuration() -> None:
    assert validate_configuration(FIXTURES / "minimal.sln", "Profile|ARM64") is False


def test_validate_configuration_tolerates_missing_section_gracefully() -> None:
    assert (
        validate_configuration(FIXTURES / "no_config_section.sln", "Release|x64") is False
    )


def test_validate_configuration_parses_slnx_cross_product() -> None:
    """A .slnx lists BuildType and Platform separately; the solution
    configurations are their cross product."""
    assert validate_configuration(FIXTURES / "minimal.slnx", "RelWithDebInfo|x64") is True
    assert validate_configuration(FIXTURES / "minimal.slnx", "Debug|x64") is True


def test_validate_configuration_rejects_missing_configuration_in_slnx() -> None:
    """The CMake-generated .slnx never declares the MTDLL flavors."""
    assert validate_configuration(FIXTURES / "minimal.slnx", "Debug-MTDLL|x64") is False


def test_validate_configuration_tolerates_malformed_slnx_gracefully() -> None:
    assert validate_configuration(FIXTURES / "malformed.slnx", "Debug|x64") is False


def test_discover_sln_returns_none_when_no_sln(tmp_path: Path) -> None:
    project_dir = tmp_path / "fake-project"
    (project_dir / "projects").mkdir(parents=True)
    assert discover_sln(project_dir, "projects", "*.sln*") is None


def test_discover_sln_returns_single_sln(tmp_path: Path) -> None:
    project_dir = tmp_path / "fake-project"
    sln_dir = project_dir / "projects"
    sln_dir.mkdir(parents=True)
    sln = sln_dir / "only.sln"
    sln.write_text("dummy", encoding="utf-8")
    assert discover_sln(project_dir, "projects", "*.sln*") == sln


def test_discover_sln_returns_single_slnx(tmp_path: Path) -> None:
    """CMake-based projects (leptonica, tesseract) ship only a .slnx; the
    `*.sln*` glob must pick it up."""
    project_dir = tmp_path / "fake-project"
    sln_dir = project_dir / "projects"
    sln_dir.mkdir(parents=True)
    slnx = sln_dir / "leptonica.slnx"
    slnx.write_text("dummy", encoding="utf-8")
    assert discover_sln(project_dir, "projects", "*.sln*") == slnx


def test_discover_sln_prefers_project_sln_when_multiple(tmp_path: Path) -> None:
    project_dir = tmp_path / "fake-project"
    sln_dir = project_dir / "projects"
    sln_dir.mkdir(parents=True)
    (sln_dir / "old.sln").write_text("dummy", encoding="utf-8")
    preferred = sln_dir / "project.sln"
    preferred.write_text("dummy", encoding="utf-8")
    assert discover_sln(project_dir, "projects", "*.sln*") == preferred


def test_discover_sln_returns_none_when_multiple_and_ambiguous(tmp_path: Path) -> None:
    """Two non-curated solutions and no project.sln: refuse to guess."""
    project_dir = tmp_path / "fake-project"
    sln_dir = project_dir / "projects"
    sln_dir.mkdir(parents=True)
    (sln_dir / "one.sln").write_text("dummy", encoding="utf-8")
    (sln_dir / "two.slnx").write_text("dummy", encoding="utf-8")
    assert discover_sln(project_dir, "projects", "*.sln*") is None


def test_validate_configuration_does_not_leak_file_handle(tmp_path: Path) -> None:
    """`with open` is required; on Windows a leaked handle blocks deletion."""
    sln = tmp_path / "ephemeral.sln"
    sln.write_text(
        (FIXTURES / "minimal.sln").read_text(encoding="utf-8"), encoding="utf-8"
    )
    assert validate_configuration(sln, "Release|x64") is True
    sln.unlink()
