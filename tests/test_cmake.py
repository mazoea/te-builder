"""Tests for te_builder.cmake."""

from __future__ import annotations

from pathlib import Path

from te_builder.cmake import discover_cmaker


def test_discover_cmaker_returns_path_when_present(tmp_path: Path) -> None:
    project_dir = tmp_path / "cmake-project"
    project_dir.mkdir()
    batch = project_dir / "cmaker.bat"
    batch.write_text("@echo off\n", encoding="utf-8")
    assert discover_cmaker(project_dir, "cmaker.bat") == batch


def test_discover_cmaker_returns_none_when_absent(tmp_path: Path) -> None:
    project_dir = tmp_path / "no-cmake"
    project_dir.mkdir()
    assert discover_cmaker(project_dir, "cmaker.bat") is None


def test_discover_cmaker_finds_batch_in_parent(tmp_path: Path) -> None:
    """te-external-leptonica / -tesseract keep cmaker.bat one level above
    the cmake project subdirectory it cd's into."""
    repo = tmp_path / "te-external-leptonica"
    project_dir = repo / "leptonica"
    project_dir.mkdir(parents=True)
    batch = repo / "cmaker.bat"
    batch.write_text("@echo off\n", encoding="utf-8")
    assert discover_cmaker(project_dir, "cmaker.bat") == batch


def test_discover_cmaker_prefers_project_dir_over_parent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    project_dir = repo / "project"
    project_dir.mkdir(parents=True)
    (repo / "cmaker.bat").write_text("@echo off\n", encoding="utf-8")
    here = project_dir / "cmaker.bat"
    here.write_text("@echo off\n", encoding="utf-8")
    assert discover_cmaker(project_dir, "cmaker.bat") == here
