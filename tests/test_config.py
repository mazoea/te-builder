"""Tests for te_builder.config.

These pin behaviour that was broken or implicit in the legacy settings.py:
- nested dict merge (`extend_dict`) preserves keys not present in the override,
- configurations stay ordered (legacy code used a `set` literal, so iteration
  order was implementation-defined and varied between runs),
- presets load from JSON without surprises.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from te_builder.config import Env, extend_dict, load_preset

FIXTURES = Path(__file__).parent / "fixtures"


def test_extend_dict_merges_nested_dicts() -> None:
    base = {"a": 1, "nested": {"x": 10, "y": 20}, "list": [1, 2]}
    override = {"nested": {"y": 99, "z": 30}, "new": "value"}
    extend_dict(base, override)
    assert base == {
        "a": 1,
        "nested": {"x": 10, "y": 99, "z": 30},
        "list": [1, 2],
        "new": "value",
    }


def test_extend_dict_replaces_non_dict_values() -> None:
    base = {"list": [1, 2], "scalar": "old"}
    override = {"list": [3, 4], "scalar": "new"}
    extend_dict(base, override)
    assert base == {"list": [3, 4], "scalar": "new"}


def test_load_preset_basic_reads_projects_and_configurations() -> None:
    env = load_preset(FIXTURES / "preset_basic.json")
    assert isinstance(env, Env)
    assert [project.name for project in env.projects] == ["zlib", "libpng"]
    assert env.projects[0].path == "te-external/zlib/"
    assert env.configurations == ["Release|x64", "Debug-MTDLL|x64"]


def test_configurations_default_is_ordered_list() -> None:
    """Regression: legacy settings.py used a set literal, which made
    configuration order non-deterministic. The default must be a list."""
    env = Env.defaults()
    assert isinstance(env.configurations, list)
    assert env.configurations == sorted(env.configurations, key=env.configurations.index)


def test_load_preset_missing_file_raises_filenotfound() -> None:
    with pytest.raises(FileNotFoundError):
        load_preset(FIXTURES / "does-not-exist.json")


def test_load_preset_overrides_default_configurations() -> None:
    env = load_preset(FIXTURES / "preset_basic.json")
    default = Env.defaults()
    assert env.configurations != default.configurations
    assert env.configurations == ["Release|x64", "Debug-MTDLL|x64"]


def test_env_project_defaults_carry_through() -> None:
    env = load_preset(FIXTURES / "preset_basic.json")
    assert env.project_defaults.parallel >= 1
    assert "projects/output/*.lib" in env.project_defaults.copy
