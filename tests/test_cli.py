"""Tests for the te_builder CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from te_builder.cli import build_parser, main, resolve_preset_path


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
