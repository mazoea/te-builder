"""Configuration model for te-builder.

`Env` is the merged view of defaults + preset JSON + CLI overrides that the
rest of the package consumes. The dataclasses are deliberately frozen so a
mis-spelled key raises at construction time rather than failing silently the
way the legacy free-form dict did.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)


_DEFAULT_CONFIGURATIONS: tuple[str, ...] = (
    "Release|x64",
    "RelWithDebInfo|x64",
    "Debug-MTDLL|x64",
    "Release-MTDLL|x64",
)


_DEFAULT_COPY_GLOBS: tuple[str, ...] = (
    "projects/output/*.lib",
    "projects/output/*.dll",
    "projects/output/*.exp",
    "bins/*.lib",
    "bins/*.exe",
    "bins/*.dll",
)


_DEFAULT_CLEANUP_GLOBS: tuple[str, ...] = (
    "projects/output/*.exe",
    "projects/output/*.lib",
    "projects/output/*.dll",
    "projects/output/*.ilk",
    "projects/output/pdb/*.pdb",
    "libs/*.lib",
    "libs/*.dll",
    "bins/*.dll",
    "bins/*.exe",
)


@dataclass(frozen=True)
class ProjectSpec:
    name: str
    path: str
    try_count: int = 0


@dataclass(frozen=True)
class ProjectDefaults:
    cmake_batch: str = "cmaker.bat"
    solution_path: str = "projects"
    solution: str = "*.sln"
    output_libs: str = "libs"
    parallel: int = 2
    copy: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_COPY_GLOBS)
    cleanup: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_CLEANUP_GLOBS)


@dataclass
class Env:
    """Mutable runtime environment.

    Not frozen because the CLI layer reassigns msvc_toolset / project_root /
    log_dir based on argparse flags. Fields are typed so callers cannot
    accidentally stuff a free-form key in.
    """

    projects: list[ProjectSpec]
    configurations: list[str]
    project_defaults: ProjectDefaults
    project_root: Path
    log_dir: Path
    msvc_toolset: str = "/p:PlatformToolset=v143"
    msvc_toolset_template: str = "/p:PlatformToolset=%s"
    msvc_builder: str = "msbuild"
    dev_platform: str | None = None
    use_cmd: bool = False
    cmd_prefix: str = ""
    cmd_suffix: str = ""
    lines_to_show: int = 20
    name: str = "te-builder"

    @classmethod
    def defaults(cls) -> Env:
        here = Path(__file__).resolve()
        return cls(
            projects=[],
            configurations=list(_DEFAULT_CONFIGURATIONS),
            project_defaults=ProjectDefaults(),
            project_root=(here.parents[2] / "..").resolve(),
            log_dir=(here.parents[2] / "_logs").resolve(),
        )


def extend_dict(target: dict[str, Any], override: dict[str, Any]) -> None:
    """Recursively merge `override` into `target` in place.

    Lists and scalars are replaced wholesale; nested dicts are merged. This
    matches the legacy semantics so JSON presets keep working unchanged.
    """
    for key, value in override.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            extend_dict(target[key], value)
        else:
            target[key] = value


def _parse_project(raw: dict[str, Any]) -> ProjectSpec:
    if "name" not in raw or "path" not in raw:
        raise ValueError(f"project entry requires name and path: {raw!r}")
    return ProjectSpec(
        name=str(raw["name"]),
        path=str(raw["path"]),
        try_count=int(raw.get("try", 0)),
    )


def load_preset(path: str | Path) -> Env:
    """Load a JSON preset and return the merged `Env`.

    Raises `FileNotFoundError` if the path does not exist — no silent
    fallbacks. The base layer is `Env.defaults()`; preset values override.
    """
    preset_path = Path(path)
    if not preset_path.is_file():
        raise FileNotFoundError(f"preset file not found: {preset_path}")
    with preset_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"preset must be a JSON object, got {type(raw).__name__}")

    env = Env.defaults()
    if "projects" in raw:
        env.projects = [_parse_project(item) for item in raw["projects"]]
    if "configurations" in raw:
        env.configurations = list(raw["configurations"])
    if "lines_to_show" in raw:
        env.lines_to_show = int(raw["lines_to_show"])
    if "name" in raw:
        env.name = str(raw["name"])
    _logger.debug("loaded preset %s with %d projects", preset_path, len(env.projects))
    return env
