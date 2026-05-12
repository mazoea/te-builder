"""te-builder command-line interface.

Replaces the legacy `main.py` script with a focused argparse-based entry
point. The interactive numbered menu, the `--settings=key=value` magic, and
the Python-2 compatibility layer are all gone — pass `--preset NAME` or use
`scripts/startme.bat` for an interactive launcher.

Public surface:
- `build_parser()` returns the argparse parser (exposed so tests can drive
  --help and option parsing without spawning a subprocess).
- `resolve_preset_path(name_or_path)` looks up a preset under the packaged
  `presets/` directory or treats the input as a literal file path.
- `main(argv)` is the script entry point used by both the console-script
  `te-builder` and `python -m te_builder`.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from importlib import resources
from pathlib import Path

from . import __version__
from .config import Env, ProjectSpec, load_preset
from .msbuild import discover_sln, validate_configuration
from .orchestration import (
    cleanup_libs_for_configuration,
    configuration_lib_dir,
    copy_libs_for_configuration,
    retry_build,
)
from .runner import run
from .status import StatusRow

_logger = logging.getLogger(__name__)
_PRESETS_PACKAGE = "te_builder.presets"


def list_packaged_presets() -> list[str]:
    return sorted(
        Path(entry.name).stem
        for entry in resources.files(_PRESETS_PACKAGE).iterdir()
        if entry.name.endswith(".json")
    )


def resolve_preset_path(name_or_path: str) -> Path:
    """Return the path to the preset JSON.

    Order of resolution:
    1. If the input is an existing file, use it as-is.
    2. If a packaged preset matches the input (with or without .json),
       return its filesystem path.
    Otherwise raise FileNotFoundError — no silent fallback.
    """
    candidate = Path(name_or_path)
    if candidate.is_file():
        return candidate
    stem = name_or_path[:-5] if name_or_path.endswith(".json") else name_or_path
    packaged = resources.files(_PRESETS_PACKAGE) / f"{stem}.json"
    if packaged.is_file():
        return Path(str(packaged))
    raise FileNotFoundError(
        f"unknown preset {name_or_path!r}; "
        f"available: {', '.join(list_packaged_presets())}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="te-builder",
        description="Orchestrate MSBuild / cmake builds of the Mazoea native deps.",
    )
    parser.add_argument(
        "--preset",
        help="Preset name (e.g. externals.basic) or path to a custom JSON preset.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Directory containing sibling te-external* checkouts. "
        "Default: two levels above this package.",
    )
    parser.add_argument(
        "--msvc-toolset",
        default="v143",
        help="MSVC toolset version (e.g. v142, v143). Default: v143.",
    )
    parser.add_argument(
        "--dev-prompt",
        help="Platform toolset to inject through the Developer prompt "
        "(rare; used when running outside Developer PowerShell).",
    )
    parser.add_argument(
        "--configurations",
        nargs="+",
        help="Override the configurations from the preset.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the build plan without invoking MSBuild.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--version", action="version", version=f"te-builder {__version__}"
    )
    return parser


def _print_preset_listing() -> None:
    sys.stderr.write("Pass --preset NAME. Available packaged presets:\n")
    for name in list_packaged_presets():
        sys.stderr.write(f"  - {name}\n")


def _apply_overrides(env: Env, args: argparse.Namespace) -> Env:
    if args.configurations:
        env.configurations = list(args.configurations)
    if args.project_root is not None:
        env.project_root = args.project_root.resolve()
    if args.msvc_toolset:
        env.msvc_toolset = env.msvc_toolset_template % args.msvc_toolset
    if args.dev_prompt:
        env.dev_platform = args.dev_prompt
    env.log_dir = env.log_dir.resolve()
    return env


def _msbuild_command(
    env: Env, sln_file: Path, configuration: str, log_file: Path, parallel: int
) -> str:
    conf, platform = configuration.split("|")
    return (
        f"{env.cmd_prefix}{env.msvc_builder} {env.msvc_toolset} "
        f'"{sln_file}" /t:rebuild '
        f'"/p:configuration={conf},platform={platform}" /m:{parallel} '
        f'"/fileLoggerParameters:LogFile={log_file}" /nologo{env.cmd_suffix}'
    )


def _build_one(
    env: Env,
    project: ProjectSpec,
    project_dir: Path,
    configuration: str,
) -> StatusRow:
    log_name = f"{project.name}.{configuration.replace('|', '-')}.log"
    log_file = env.log_dir / log_name
    sln = discover_sln(
        project_dir, env.project_defaults.solution_path, env.project_defaults.solution
    )
    if sln is None:
        return StatusRow(
            ok=False,
            line=f"{project.name:>15} : {configuration:>20} : NO SOLUTION !!!!",
        )
    if not validate_configuration(sln, configuration):
        return StatusRow(
            ok=False,
            line=f"{project.name:>15} : {configuration:>20} : MISSING CFG !!!!",
        )
    cmd = _msbuild_command(
        env, sln, configuration, log_file, env.project_defaults.parallel
    )

    def attempt() -> int:
        result = run(cmd, shell=True)
        return result.returncode

    rc = retry_build(attempt, max_retries=project.try_count)
    if rc == 0:
        return StatusRow(ok=True, line=f"{project.name:>15} : {configuration:>20} : OK")
    return StatusRow(
        ok=False,
        line=f"{project.name:>15} : {configuration:>20} : FAILED rc={rc} !!!!",
    )


def _build_loop(env: Env) -> tuple[list[StatusRow], int]:
    rows: list[StatusRow] = []
    rc = 0
    for configuration in env.configurations:
        for project in env.projects:
            project_dir = (env.project_root / project.path).resolve()
            _logger.info(
                "build [%s] config=[%s] dir=[%s]",
                project.name,
                configuration,
                project_dir,
            )
            cleanup_libs_for_configuration(
                project_dir, configuration, env.project_defaults
            )
            row = _build_one(env, project, project_dir, configuration)
            rows.append(row)
            if not row.ok:
                rc = 1
            if row.ok:
                copy_libs_for_configuration(
                    project_dir, configuration, env.project_defaults
                )
                _logger.info(
                    "artifacts in %s",
                    configuration_lib_dir(
                        project_dir, configuration, env.project_defaults
                    ),
                )
    return rows, rc


def _emit_summary(rows: list[StatusRow], elapsed: float) -> None:
    for row in rows:
        _logger.info(row.line)
    _logger.info("finished in %.2fs", elapsed)


def _print_dry_run_plan(env: Env, preset_path: Path) -> None:
    out = sys.stdout
    out.write(f"Preset: {preset_path}\n")
    out.write(f"Project root: {env.project_root}\n")
    out.write("Configurations:\n")
    for cfg in env.configurations:
        out.write(f"  - {cfg}\n")
    out.write("Projects:\n")
    for project in env.projects:
        out.write(f"  - {project.name} ({project.path})\n")
    out.flush()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname).4s %(name)s %(message)s",
    )
    if not args.preset:
        _print_preset_listing()
        return 2
    try:
        preset_path = resolve_preset_path(args.preset)
    except FileNotFoundError as exc:
        _logger.error("%s", exc)
        _print_preset_listing()
        return 2

    env = load_preset(preset_path)
    env = _apply_overrides(env, args)
    env.log_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        _print_dry_run_plan(env, preset_path)
        return 0

    start = time.perf_counter()
    rows, rc = _build_loop(env)
    _emit_summary(rows, time.perf_counter() - start)
    return rc


if __name__ == "__main__":
    sys.exit(main())
