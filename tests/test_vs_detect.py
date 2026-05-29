"""Tests for te_builder.vs_detect.

Three concerns are pinned here:
- `vswhere.exe` JSON output is parsed into typed VsInstall records and the
  major version is mapped to the right MSVC platform toolset (v141 for
  VS 2017, v142 for VS 2019, v143 for VS 2022, v145 for VS 2026 — the
  latter skips v144);
- `select_toolset()` is non-interactive when stdin isn't a TTY (CI), so
  pipelines never hang on a prompt;
- when interactive, the prompt callable is injected so the test can drive
  the menu without touching real stdin.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from te_builder.vs_detect import (
    VsInstall,
    main,
    parse_vswhere_output,
    select_toolset,
    toolset_for_version,
)

_FAKE_VSWHERE = json.dumps(
    [
        {
            "instanceId": "abc",
            "installationVersion": "17.8.34316.72",
            "installationPath": "C:\\VS\\2022",
            "displayName": "Visual Studio Community 2022",
            "productLineVersion": "2022",
        },
        {
            "instanceId": "def",
            "installationVersion": "18.0.1234.0",
            "installationPath": "C:\\VS\\2026",
            "displayName": "Visual Studio Enterprise 2026",
            "productLineVersion": "2026",
        },
    ]
)


def test_toolset_for_version_known_majors() -> None:
    assert toolset_for_version("15.0.0") == "v141"
    assert toolset_for_version("16.11.34") == "v142"
    assert toolset_for_version("17.8.0") == "v143"
    assert toolset_for_version("18.0.0") == "v145"


def test_toolset_for_version_unknown_returns_none() -> None:
    assert toolset_for_version("99.0.0") is None
    assert toolset_for_version("") is None


def test_parse_vswhere_output_returns_typed_installs() -> None:
    installs = parse_vswhere_output(_FAKE_VSWHERE)
    assert [inst.display_name for inst in installs] == [
        "Visual Studio Community 2022",
        "Visual Studio Enterprise 2026",
    ]
    assert installs[0].toolset == "v143"
    assert installs[1].toolset == "v145"
    assert installs[0].installation_path == Path("C:\\VS\\2022")


def test_parse_vswhere_skips_entries_without_known_toolset() -> None:
    raw = json.dumps([{"installationVersion": "99.0.0", "displayName": "Future"}])
    assert parse_vswhere_output(raw) == []


def test_parse_vswhere_handles_empty_output() -> None:
    assert parse_vswhere_output("") == []
    assert parse_vswhere_output("[]") == []


def test_select_toolset_returns_single_install_silently() -> None:
    install = VsInstall(
        display_name="VS 2022",
        installation_path=Path("C:\\VS\\2022"),
        installation_version="17.8.0",
        toolset="v143",
    )
    chosen = select_toolset([install], interactive=False)
    assert chosen == "v143"


def test_select_toolset_picks_highest_when_not_interactive() -> None:
    chosen = select_toolset(parse_vswhere_output(_FAKE_VSWHERE), interactive=False)
    assert chosen == "v145"


def test_select_toolset_prompts_when_interactive() -> None:
    """The menu lists highest-major first; '2' picks the second-ranked
    install (VS 2022 -> v143)."""
    installs = parse_vswhere_output(_FAKE_VSWHERE)
    answers = iter(["2"])
    chosen = select_toolset(installs, interactive=True, prompt=lambda _msg: next(answers))
    assert chosen == "v143"


def test_select_toolset_reprompts_on_invalid_input() -> None:
    """Garbage and out-of-range entries re-prompt; '1' selects the
    highest-ranked install (VS 2026 -> v145)."""
    installs = parse_vswhere_output(_FAKE_VSWHERE)
    answers = iter(["garbage", "9", "1"])
    chosen = select_toolset(installs, interactive=True, prompt=lambda _msg: next(answers))
    assert chosen == "v145"


def test_select_toolset_returns_none_when_no_installs() -> None:
    assert select_toolset([], interactive=False) is None
    assert select_toolset([], interactive=True, prompt=lambda _msg: "1") is None


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_select_toolset_blank_prompt_uses_default(blank: str) -> None:
    """A blank answer defaults to the highest-ranked install (v145)."""
    installs = parse_vswhere_output(_FAKE_VSWHERE)
    chosen = select_toolset(installs, interactive=True, prompt=lambda _msg: blank)
    assert chosen == "v145"


def test_main_toolset_prints_highest_detected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--toolset` is the machine-readable mode shell scripts in sibling
    repos rely on. Stdout must hold only the toolset short name so a `for /f`
    or `$(...)` capture binds cleanly."""
    monkeypatch.setattr(
        "te_builder.vs_detect.detect_installs",
        lambda: parse_vswhere_output(_FAKE_VSWHERE),
    )
    rc = main(["--toolset"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out == "v145\n"


def test_main_toolset_no_installs_exits_nonzero_with_empty_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A consumer in cmaker.bat applies its own fallback when nothing is
    detected. Exit 1 + empty stdout keeps that contract — caller checks
    errorlevel without parsing prose."""
    monkeypatch.setattr("te_builder.vs_detect.detect_installs", lambda: [])
    rc = main(["--toolset"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == ""


def test_main_default_lists_installs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No flag preserves the human-readable listing wired into list-vs.bat."""
    monkeypatch.setattr(
        "te_builder.vs_detect.detect_installs",
        lambda: parse_vswhere_output(_FAKE_VSWHERE),
    )
    rc = main([])
    captured = capsys.readouterr()
    assert rc == 0
    assert "Visual Studio Enterprise 2026" in captured.out
    assert "v145" in captured.out
