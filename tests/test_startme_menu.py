"""Unit tests for the reusable startme launcher (`tools/startme/menu.py`).

Exercises only the pure-logic helpers — no TTY, no subprocess. The launcher
itself is vendored from an internal upstream launcher project; these tests
are the local contract we want to keep stable as we curate `scripts.yaml`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from menu import (
    InputSpec,
    ScriptItem,
    _load_script,
    _matches_any,
    build_argv,
)


def test_build_argv_for_bat_uses_cmd_on_windows() -> None:
    item = ScriptItem(
        id="x",
        section="setup",
        path="scripts/startme.bat",
        label="x",
        description="",
    )
    argv = build_argv(item, Path("/repo"), platform_os="nt")
    assert argv[0] == "cmd"
    assert argv[1] == "/c"
    assert argv[-1].endswith("startme.bat")


def test_build_argv_for_bat_raises_outside_windows() -> None:
    item = ScriptItem(
        id="x",
        section="setup",
        path="scripts/startme.bat",
        label="x",
        description="",
    )
    with pytest.raises(RuntimeError):
        build_argv(item, Path("/repo"), platform_os="posix")


def test_build_argv_for_py_uses_current_interpreter() -> None:
    item = ScriptItem(
        id="x",
        section="dev",
        path="tools/example/run.py",
        label="x",
        description="",
    )
    argv = build_argv(item, Path("/repo"), platform_os="nt")
    assert argv[0] == sys.executable
    assert argv[-1].endswith("run.py")


def test_build_argv_passes_through_args() -> None:
    item = ScriptItem(
        id="x",
        section="dev",
        path="tools/example/run.py",
        label="x",
        description="",
        args=("--flag", "value"),
    )
    argv = build_argv(item, Path("/repo"), platform_os="nt")
    assert argv[-2:] == ["--flag", "value"]


def test_matches_any_glob() -> None:
    assert _matches_any("tools/data/x.json", ("tools/data/**",))
    assert not _matches_any("tools/keep.py", ("tools/data/**",))


def test_load_script_requires_path() -> None:
    with pytest.raises(ValueError, match="path"):
        _load_script({"id": "no-path"})


def test_load_script_requires_id_or_falls_back_to_stem() -> None:
    item = _load_script({"path": "scripts/foo.bat"})
    assert item.id == "foo"
    assert item.label == "foo.bat"


def test_inputspec_defaults() -> None:
    spec = InputSpec(name="kind", prompt="kind?")
    assert spec.passthrough is True
    assert spec.required is False
    assert spec.default is None
