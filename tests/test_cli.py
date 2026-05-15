"""Tests for the te_builder CLI."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from te_builder import cli
from te_builder.cli import (
    _build_loop,
    _build_one,
    _build_with_cmaker,
    _cmaker_toolset,
    _emit_summary,
    build_parser,
    main,
    resolve_preset_path,
)
from te_builder.config import Env, ProjectSpec
from te_builder.runner import RunResult
from te_builder.status import StatusRow


def _failed_run(*_args: object, **_kwargs: object) -> RunResult:
    return RunResult(returncode=1, stdout="", stderr="", took=0.0)


def test_parser_help_lists_main_flags(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["--help"])
    assert info.value.code == 0
    captured = capsys.readouterr()
    for flag in ("--preset", "--project-root", "--dry-run", "--msvc-toolset"):
        assert flag in captured.out


def test_resolve_preset_path_uses_packaged_directory() -> None:
    path = resolve_preset_path("externals.basic")
    assert path.name == "externals.basic.json"
    assert path.is_file()


def test_resolve_preset_path_accepts_file_path(tmp_path: Path) -> None:
    custom = tmp_path / "my-preset.json"
    custom.write_text(json.dumps({"projects": []}), encoding="utf-8")
    resolved = resolve_preset_path(str(custom))
    assert resolved == custom


def test_resolve_preset_path_unknown_raises_filenotfound() -> None:
    with pytest.raises(FileNotFoundError):
        resolve_preset_path("does-not-exist-anywhere")


def test_main_returns_2_on_missing_preset(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["--preset", "does-not-exist"])
    assert rc == 2


def test_main_lists_presets_when_called_without_preset(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main([])
    assert rc == 2
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "externals.basic" in combined


def test_main_dry_run_does_not_invoke_runner(tmp_path: Path) -> None:
    rc = main(["--preset", "externals.basic", "--dry-run"])
    assert rc == 0


def test_main_dry_run_lists_planned_projects(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main(["--preset", "externals.basic", "--dry-run"])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "zlib" in combined
    assert "libpng" in combined


def test_main_rejects_configuration_without_pipe(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without the `Config|Platform` shape, MSBuild dispatch can't split
    the value. Reject up front rather than crashing later."""
    with pytest.raises(SystemExit) as info:
        main(["--preset", "externals.basic", "--dry-run", "--configurations", "Release"])
    assert info.value.code == 2
    captured = capsys.readouterr()
    assert "Config|Platform" in captured.err


def test_main_accepts_valid_configuration_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "--preset",
            "externals.basic",
            "--dry-run",
            "--configurations",
            "Release|x64",
            "Debug-MTDLL|x64",
        ]
    )
    assert rc == 0


def test_parser_accepts_repeated_preset() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["--preset", "externals.basic", "--preset", "minimal_configurations"]
    )
    assert args.preset == ["externals.basic", "minimal_configurations"]


def test_main_merges_preset_overlay_in_dry_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """externals.basic supplies the projects; minimal_configurations
    overlays the MT configurations on top."""
    rc = main(
        [
            "--preset",
            "externals.basic",
            "--preset",
            "minimal_configurations",
            "--dry-run",
        ]
    )
    assert rc == 0
    combined = "".join(capsys.readouterr())
    assert "zlib" in combined
    assert "Debug-MT|x64" in combined


def test_cmaker_toolset_extracts_bare_version() -> None:
    env = Env.defaults()
    env.msvc_toolset = "/p:PlatformToolset=v145"
    assert _cmaker_toolset(env) == "v145"


def test_build_one_reports_no_solution(tmp_path: Path) -> None:
    env = Env.defaults()
    env.log_dir = tmp_path / "logs"
    project = ProjectSpec(name="x", path="proj/")
    project_dir = tmp_path / "proj"
    (project_dir / "projects").mkdir(parents=True)
    row = _build_one(env, project, project_dir, "Release|x64")
    assert not row.ok
    assert "NO SOLUTION" in row.line


def test_build_with_cmaker_runs_cmaker_and_reports_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cmaker = tmp_path / "cmaker.bat"
    cmaker.write_text("@echo off\n", encoding="utf-8")
    env = Env.defaults()
    env.log_dir = tmp_path / "logs"
    project = ProjectSpec(name="leptonica", path="x/")

    calls: dict[str, object] = {}

    def fake_run(cmd: str, *, cwd: object = None, shell: bool = False) -> RunResult:
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return RunResult(returncode=0, stdout="0 Error(s)", stderr="", took=0.0)

    monkeypatch.setattr(cli, "run", fake_run)
    row = _build_with_cmaker(env, project, tmp_path / "x", cmaker)

    assert row.ok
    assert "leptonica" in row.line
    assert "VSTOOLSET" in str(calls["cmd"])
    assert str(cmaker) in str(calls["cmd"])
    assert calls["cwd"] == cmaker.parent


def test_build_with_cmaker_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cmaker = tmp_path / "cmaker.bat"
    cmaker.write_text("@echo off\n", encoding="utf-8")
    env = Env.defaults()
    env.log_dir = tmp_path / "logs"
    project = ProjectSpec(name="leptonica", path="x/")
    monkeypatch.setattr(cli, "run", _failed_run)
    row = _build_with_cmaker(env, project, tmp_path / "x", cmaker)
    assert not row.ok


def test_build_loop_runs_cmaker_once_regardless_of_configurations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project shipping cmaker.bat is built once end-to-end — cmaker.bat
    owns the configuration set, so the preset's two configurations do not
    each trigger a build."""
    project_dir = tmp_path / "ext" / "leptonica"
    project_dir.mkdir(parents=True)
    (tmp_path / "ext" / "cmaker.bat").write_text("@echo off\n", encoding="utf-8")

    env = Env.defaults()
    env.project_root = tmp_path
    env.log_dir = tmp_path / "logs"
    env.configurations = ["Debug|x64", "RelWithDebInfo|x64"]
    env.projects = [ProjectSpec(name="leptonica", path="ext/leptonica/")]

    runs: list[object] = []

    def fake_run(cmd: str, *, cwd: object = None, shell: bool = False) -> RunResult:
        runs.append(cmd)
        return RunResult(returncode=0, stdout="0 Error(s)", stderr="", took=0.0)

    monkeypatch.setattr(cli, "run", fake_run)
    rows, rc = _build_loop(env)

    assert rc == 0
    assert len(runs) == 1
    assert "cmaker.bat" in str(runs[0])
    assert [row.ok for row in rows] == [True]


def test_build_loop_msbuild_project_builds_per_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project without a cmaker.bat is driven through MSBuild once per
    configuration."""
    project_dir = tmp_path / "ext" / "zlib"
    (project_dir / "projects").mkdir(parents=True)

    env = Env.defaults()
    env.project_root = tmp_path
    env.log_dir = tmp_path / "logs"
    env.configurations = ["Debug-MTDLL|x64", "Release-MTDLL|x64"]
    env.projects = [ProjectSpec(name="zlib", path="ext/zlib/")]

    monkeypatch.setattr(
        cli, "discover_sln", lambda *a, **k: project_dir / "projects" / "project.sln"
    )
    monkeypatch.setattr(cli, "validate_configuration", lambda *a, **k: True)
    runs: list[object] = []

    def fake_run(cmd: str, *, cwd: object = None, shell: bool = False) -> RunResult:
        runs.append(cmd)
        return RunResult(returncode=0, stdout="0 Error(s)", stderr="", took=0.0)

    monkeypatch.setattr(cli, "run", fake_run)
    rows, rc = _build_loop(env)

    assert rc == 0
    assert len(runs) == 2
    assert [row.ok for row in rows] == [True, True]


def test_build_with_cmaker_status_is_ok_not_msbuild_error_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cmaker status is always 'OK' on success, even when the log contains
    the MSBuild '0 Error(s)' line — so output is consistent across
    projects whose cmaker.bat does or does not invoke MSBuild directly."""
    cmaker = tmp_path / "cmaker.bat"
    cmaker.write_text("@echo off\n", encoding="utf-8")
    env = Env.defaults()
    env.log_dir = tmp_path / "logs"
    project = ProjectSpec(name="leptonica", path="x/")

    def fake_run_with_msbuild_output(
        cmd: str, *, cwd: object = None, shell: bool = False
    ) -> RunResult:
        return RunResult(returncode=0, stdout="0 Error(s)", stderr="", took=0.0)

    monkeypatch.setattr(cli, "run", fake_run_with_msbuild_output)
    row = _build_with_cmaker(env, project, tmp_path / "x", cmaker)

    assert row.ok
    assert "OK" in row.line
    assert "Error(s)" not in row.line


def test_build_with_cmaker_failure_line_contains_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cmaker = tmp_path / "cmaker.bat"
    cmaker.write_text("@echo off\n", encoding="utf-8")
    env = Env.defaults()
    env.log_dir = tmp_path / "logs"
    project = ProjectSpec(name="leptonica", path="x/")
    monkeypatch.setattr(cli, "run", _failed_run)
    row = _build_with_cmaker(env, project, tmp_path / "x", cmaker)
    assert not row.ok
    assert "FAILED" in row.line


def test_emit_summary_reports_all_passed(caplog: pytest.LogCaptureFixture) -> None:
    rows = [
        StatusRow(ok=True, line="zlib : Release|x64 : 0 Error(s)"),
        StatusRow(ok=True, line="libpng : Release|x64 : 0 Error(s)"),
    ]
    with caplog.at_level(logging.INFO, logger="te_builder.cli"):
        _emit_summary(rows, elapsed=12.3)
    assert "all 2 passed" in caplog.text


def test_emit_summary_reports_failure_count(caplog: pytest.LogCaptureFixture) -> None:
    rows = [
        StatusRow(ok=True, line="zlib : Release|x64 : 0 Error(s)"),
        StatusRow(ok=False, line="libpng : Release|x64 : FAILED"),
    ]
    with caplog.at_level(logging.INFO, logger="te_builder.cli"):
        _emit_summary(rows, elapsed=5.0)
    assert "1/2 FAILED" in caplog.text
