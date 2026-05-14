"""Colorized interactive launcher for project scripts.

Launched by scripts/startme.bat. The menu is reusable across projects: script
metadata lives in scripts.yaml, while discovery fills in candidates that do not
yet have curated descriptions.
"""
from __future__ import annotations

import argparse
import fnmatch
import logging
import os
import shlex
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised by users without deps
    raise SystemExit(
        "PyYAML is required. Install it with: "
        "python -m pip install -r tools/startme/requirements.txt"
    ) from exc

try:
    from tqdm import tqdm
except ImportError as exc:  # pragma: no cover - exercised by users without deps
    raise SystemExit(
        "tqdm is required. Install it with: "
        "python -m pip install -r tools/startme/requirements.txt"
    ) from exc


_logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = Path(__file__).with_name("scripts.yaml")

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
INV = "\x1b[7m"
RED = "\x1b[31m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
CYAN = "\x1b[36m"
GRAY = "\x1b[90m"
HIDE_CUR = "\x1b[?25l"
SHOW_CUR = "\x1b[?25h"
CLEAR_SCREEN = "\x1b[2J\x1b[H"
ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"


class NoTTY(Exception):
    """Stdin cannot read single keypresses."""


@dataclass(frozen=True)
class InputSpec:
    name: str
    prompt: str
    default: str | None = None
    required: bool = False
    passthrough: bool = True
    note: str = ""


@dataclass(frozen=True)
class Section:
    id: str
    title: str


@dataclass(frozen=True)
class ScriptItem:
    id: str
    section: str
    path: str
    label: str
    description: str
    command: str = ""
    when: str = ""
    prerequisites: tuple[str, ...] = ()
    inputs: tuple[InputSpec, ...] = ()
    outputs: tuple[str, ...] = ()
    args: tuple[str, ...] = ()
    cwd: str | None = None
    enabled: bool = True
    discovered: bool = False


@dataclass(frozen=True)
class LauncherConfig:
    title: str
    sections: tuple[Section, ...]
    scripts: tuple[ScriptItem, ...]
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    defaults: dict[str, bool]


@dataclass
class RuntimeOptions:
    wait_after_run: bool = True
    confirm_before_run: bool = True
    show_discovered: bool = True
    color: bool = True
    progress: bool = True
    dry_run: bool = False


def _as_str_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def _load_inputs(items: Any) -> tuple[InputSpec, ...]:
    if not items:
        return ()
    loaded: list[InputSpec] = []
    for raw in items:
        if not isinstance(raw, dict):
            raise ValueError(f"input spec must be a mapping: {raw!r}")
        name = str(raw.get("name") or "value")
        loaded.append(
            InputSpec(
                name=name,
                prompt=str(raw.get("prompt") or name),
                default=(
                    None if raw.get("default") is None else str(raw.get("default"))
                ),
                required=bool(raw.get("required", False)),
                passthrough=bool(raw.get("passthrough", True)),
                note=str(raw.get("note") or ""),
            )
        )
    return tuple(loaded)


def _load_script(raw: dict[str, Any]) -> ScriptItem:
    path = str(raw.get("path") or "")
    command = str(raw.get("command") or "")
    script_id = str(raw.get("id") or Path(path).stem).strip()
    if not script_id:
        raise ValueError(f"script id is required for {raw!r}")
    if bool(path) == bool(command):
        raise ValueError(
            f"script {script_id} needs exactly one of 'path' or 'command'"
        )
    return ScriptItem(
        id=script_id,
        section=str(raw.get("section") or "discovered"),
        path=path.replace("\\", "/"),
        command=command,
        label=str(raw.get("label") or Path(path).name or script_id),
        description=str(raw.get("description") or "No description yet."),
        when=str(raw.get("when") or ""),
        prerequisites=_as_str_list(raw.get("prerequisites")),
        inputs=_load_inputs(raw.get("inputs")),
        outputs=_as_str_list(raw.get("outputs")),
        args=_as_str_list(raw.get("args")),
        cwd=(None if raw.get("cwd") is None else str(raw.get("cwd"))),
        enabled=bool(raw.get("enabled", True)),
    )


def load_config(config_path: Path) -> LauncherConfig:
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
    except FileNotFoundError as exc:
        raise SystemExit(f"Config file not found: {config_path}") from exc
    except yaml.YAMLError as exc:
        raise SystemExit(f"Invalid YAML in {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("launcher config must be a YAML mapping")
    raw_sections = raw.get("sections") or []
    sections = tuple(
        Section(id=str(item["id"]), title=str(item.get("title") or item["id"]))
        for item in raw_sections
    )
    if not sections:
        sections = (Section(id="discovered", title="Discovered scripts"),)
    discovery = raw.get("discovery") or {}
    defaults = raw.get("defaults") or {}
    return LauncherConfig(
        title=str(raw.get("title") or "Interactive launcher"),
        sections=sections,
        scripts=tuple(_load_script(item) for item in raw.get("scripts") or []),
        include=_as_str_list(discovery.get("include")),
        exclude=_as_str_list(discovery.get("exclude")),
        defaults={str(key): bool(value) for key, value in defaults.items()},
    )


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def discover_script_paths(
    repo_root: Path,
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    *,
    show_progress: bool,
) -> list[str]:
    paths: set[str] = set()
    patterns = include or ("scripts/**/*", "tools/**/*")
    iterator = tqdm(patterns, desc="discover scripts", disable=not show_progress)
    for pattern in iterator:
        for candidate in repo_root.glob(pattern):
            if not candidate.is_file():
                continue
            rel = candidate.relative_to(repo_root).as_posix()
            if _matches_any(rel, exclude):
                continue
            if candidate.suffix.lower() not in {".bat", ".cmd", ".ps1", ".sh", ".py"}:
                continue
            paths.add(rel)
    return sorted(paths)


def _pretty_label(path: str) -> str:
    stem = Path(path).stem.replace("__", "").replace("_", " ").replace(".", " ")
    return " ".join(part.capitalize() for part in stem.split())


def _discovered_item(path: str) -> ScriptItem:
    script_id = path.replace("/", "-").replace(".", "-").lower()
    return ScriptItem(
        id=script_id,
        section="discovered",
        path=path,
        label=_pretty_label(path),
        description="Discovered runnable file without curated YAML metadata.",
        when="Review the file and add metadata to tools/startme/scripts.yaml before frequent use.",
        prerequisites=("Review the underlying script before running it.",),
        outputs=("Whatever the discovered script writes or prints.",),
        discovered=True,
    )


def build_menu_items(
    config: LauncherConfig,
    repo_root: Path,
    options: RuntimeOptions,
) -> tuple[tuple[Section, ...], list[ScriptItem]]:
    items = [item for item in config.scripts if item.enabled]
    if options.show_discovered:
        configured_paths = {item.path for item in items if item.path}
        discovered = discover_script_paths(
            repo_root,
            config.include,
            config.exclude,
            show_progress=options.progress and sys.stderr.isatty(),
        )
        for path in discovered:
            if path not in configured_paths:
                items.append(_discovered_item(path))
    section_ids = {section.id for section in config.sections}
    if any(item.section not in section_ids for item in items):
        config_sections = (*config.sections, Section(id="discovered",
                           title="Discovered scripts"))
    else:
        config_sections = config.sections
    order = {section.id: index for index, section in enumerate(config_sections)}
    items.sort(key=lambda item: (order.get(item.section, 999), item.label.lower()))
    return config_sections, items


def _enable_ansi_on_windows() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        std_out = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(std_out, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(std_out, mode.value | 0x0004))
    except Exception:
        return False


def _color(text: str, color_code: str, options: RuntimeOptions) -> str:
    if not options.color:
        return text
    return f"{color_code}{text}{RESET}"


def _resolve_path(repo_root: Path, value: str | None) -> Path:
    if not value:
        return repo_root
    path = Path(value)
    return path if path.is_absolute() else (repo_root / path).resolve()


_OPEN_WITH_SHELL = {".html", ".htm", ".md", ".pdf", ".yaml", ".yml", ".json", ".tsv", ".csv", ".txt"}


def build_argv(item: ScriptItem, repo_root: Path, *, platform_os: str = os.name) -> list[str]:
    if item.command:
        # A raw shell command instead of a wrapper script: run it through the
        # platform shell so chaining ('&&') and built-ins ('call') work as
        # written. `args` are not appended — they would land on the shell, not
        # the command, so command entries bake every argument into the string.
        shell = ["cmd", "/c"] if platform_os == "nt" else ["sh", "-c"]
        return [*shell, item.command]
    target = _resolve_path(repo_root, item.path)
    suffix = target.suffix.lower()
    extra = list(item.args)
    if suffix in {".bat", ".cmd"}:
        if platform_os != "nt":
            raise RuntimeError(f"Windows batch scripts require Windows: {item.path}")
        return ["cmd", "/c", str(target), *extra]
    if suffix == ".py":
        return [sys.executable, str(target), *extra]
    if suffix == ".sh":
        shell = "bash" if platform_os == "nt" else "sh"
        return [shell, str(target), *extra]
    if suffix == ".ps1":
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(target), *extra]
    if suffix in _OPEN_WITH_SHELL:
        if platform_os == "nt":
            # `cmd /c start "" <path>` hands the file to the Windows shell so it
            # opens with whatever app the user has registered (browser, editor).
            return ["cmd", "/c", "start", "", str(target), *extra]
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        return [opener, str(target), *extra]
    return [str(target), *extra]


def _read_key() -> str:
    if not sys.stdin.isatty():
        raise NoTTY
    if os.name == "nt":
        import msvcrt

        key = msvcrt.getch()
        if key in (b"\x00", b"\xe0"):
            return {
                b"H": "up",
                b"P": "down",
                b"K": "left",
                b"M": "right",
                b"G": "home",
                b"O": "end",
            }.get(msvcrt.getch(), "")
        if key == b"\r":
            return "enter"
        if key == b"\x1b":
            return "esc"
        if key == b"\x03":
            raise KeyboardInterrupt
        try:
            return key.decode("utf-8", errors="replace")
        except Exception:
            return ""

    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        key = sys.stdin.read(1)
        if key == "\x1b":
            if select.select([sys.stdin], [], [], 0.05)[0]:
                seq = sys.stdin.read(1)
                if seq == "[":
                    code = sys.stdin.read(1)
                    return {"A": "up", "B": "down", "C": "right", "D": "left"}.get(
                        code, ""
                    )
            return "esc"
        if key in ("\r", "\n"):
            return "enter"
        if key == "\x03":
            raise KeyboardInterrupt
        return key
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _group_by_section(sections: tuple[Section, ...], items: list[ScriptItem]) -> dict[str, list[ScriptItem]]:
    grouped = {section.id: [] for section in sections}
    for item in items:
        grouped.setdefault(item.section, []).append(item)
    return grouped


def _wrap_lines(text: str, width: int, limit: int = 3) -> list[str]:
    if not text:
        return []
    return textwrap.wrap(text, width=max(30, width))[:limit]


def _render_main(
    title: str,
    sections: tuple[Section, ...],
    grouped: dict[str, list[ScriptItem]],
    section_index: int,
    item_index: int,
    options: RuntimeOptions,
    status: str,
) -> None:
    cols, _rows = shutil.get_terminal_size((110, 32))
    cols = max(80, min(cols, 150))
    left_w = 30
    right_w = cols - left_w - 6
    current_section = sections[section_index]
    current_items = grouped.get(current_section.id, [])
    selected = current_items[item_index] if current_items else None

    sys.stdout.write(CLEAR_SCREEN if options.color else "\n")
    print(_color(title, BOLD + CYAN, options))
    print(_color("=" * min(cols, len(title) + 18), CYAN, options))
    print()
    header_left = _color(f"{'Sections':<{left_w}}", BOLD + YELLOW, options)
    print(f"{header_left} Scripts")
    rows = max(len(sections), len(current_items), 1)
    for row in range(rows):
        if row < len(sections):
            marker = ">" if row == section_index else " "
            left = f"{marker} {sections[row].title[: left_w - 4]:<{left_w - 2}}"
            if row == section_index:
                left = _color(left, INV + BOLD, options)
        else:
            left = " " * left_w
        if row < len(current_items):
            marker = ">" if row == item_index else " "
            right = f"{marker} {current_items[row].label[: right_w - 4]}"
            if row == item_index:
                right = _color(right, INV + BOLD, options)
        else:
            right = ""
        print(f"{left}  {right}")

    print()
    if selected is None:
        print(_color("No scripts in this section.", YELLOW, options))
    else:
        print(_color(selected.label, BOLD + GREEN, options))
        for line in _wrap_lines(selected.description, cols - 4):
            print(f"  {line}")
        if selected.when:
            print(_color("  When: ", BOLD, options) + selected.when)
        if selected.prerequisites:
            print(_color("  Prereqs:", BOLD, options))
            for prereq in selected.prerequisites[:4]:
                print(f"    - {prereq}")
        if selected.inputs:
            print(_color("  Inputs:", BOLD, options))
            for input_spec in selected.inputs[:4]:
                req = "required" if input_spec.required else "optional"
                print(f"    - {input_spec.name}: {input_spec.prompt} ({req})")
        if selected.outputs:
            print(_color("  Outputs:", BOLD, options))
            for output in selected.outputs[:4]:
                print(f"    - {output}")
        print(_color("  Command: ", BOLD, options) + (selected.command or selected.path))
    print()
    print(_color("Up/Down item | Left/Right section | Enter run | c config | r refresh | q quit", DIM, options))
    if status:
        print(status)
    sys.stdout.flush()


def _print_script_details(item: ScriptItem, options: RuntimeOptions) -> None:
    print(_color(item.label, BOLD + CYAN, options))
    print(item.description)
    if item.when:
        print(f"When: {item.when}")
    if item.prerequisites:
        print("Prerequisites:")
        for prereq in item.prerequisites:
            print(f"  - {prereq}")
    if item.inputs:
        print("Inputs:")
        for input_spec in item.inputs:
            default = f" default={input_spec.default}" if input_spec.default else ""
            print(f"  - {input_spec.name}: {input_spec.prompt}{default}")
            if input_spec.note:
                print(f"    {input_spec.note}")
    if item.outputs:
        print("Outputs:")
        for output in item.outputs:
            print(f"  - {output}")


def _collect_input_args(item: ScriptItem) -> list[str]:
    args: list[str] = []
    for input_spec in item.inputs:
        if not input_spec.passthrough:
            continue
        while True:
            suffix = f" [{input_spec.default}]" if input_spec.default else ""
            raw = input(f"{input_spec.prompt}{suffix}: ").strip()
            value = raw or input_spec.default or ""
            if value or not input_spec.required:
                break
            print("Value is required.")
        if value:
            args.append(value)
    return args


def _confirm(prompt: str, default: bool) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    answer = input(prompt + suffix).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def _wait_for_key() -> None:
    if not sys.stdin.isatty():
        return
    print("\nPress any key to return to the launcher...", end="", flush=True)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.getch()
        else:
            _read_key()
    except (KeyboardInterrupt, NoTTY):
        pass
    print()


def run_script(item: ScriptItem, repo_root: Path, options: RuntimeOptions) -> int:
    print()
    _print_script_details(item, options)
    print()
    try:
        argv = build_argv(item, repo_root)
    except RuntimeError as exc:
        print(_color(str(exc), RED, options))
        if options.wait_after_run:
            _wait_for_key()
        return 1
    argv.extend(_collect_input_args(item))
    cwd = _resolve_path(repo_root, item.cwd or str(Path(item.path).parent))
    pretty = " ".join(shlex.quote(part) for part in argv)
    print(_color("Command:", BOLD, options), pretty)
    print(_color("Working directory:", BOLD, options), cwd)
    if options.confirm_before_run and not options.dry_run:
        if not _confirm("Run this script?", default=False):
            print("Cancelled.")
            return 1
    if options.dry_run:
        print(_color("Dry run: command was not executed.", YELLOW, options))
        return 0
    _logger.info("running %s", pretty)
    try:
        result = subprocess.run(argv, cwd=str(cwd), check=False)
        rc = result.returncode
    except KeyboardInterrupt:
        print(_color("Interrupted.", YELLOW, options))
        rc = 130
    except FileNotFoundError as exc:
        print(_color(f"Command not found: {exc}", RED, options))
        rc = 127
    finally:
        if options.wait_after_run:
            _wait_for_key()
    return rc


def _enter_alt_screen(options: RuntimeOptions) -> None:
    if options.color:
        sys.stdout.write(ALT_SCREEN_ON + HIDE_CUR)
        sys.stdout.flush()


def _leave_alt_screen(options: RuntimeOptions) -> None:
    if options.color:
        sys.stdout.write(SHOW_CUR + ALT_SCREEN_OFF + RESET)
        sys.stdout.flush()


def _render_config(options: RuntimeOptions) -> None:
    toggles = [
        ("1", "confirm_before_run", "Ask before executing a script"),
        ("2", "wait_after_run", "Wait for a key after execution"),
        ("3", "show_discovered", "Show discovered scripts without YAML metadata"),
        ("4", "color", "Use ANSI colors"),
        ("5", "progress", "Show tqdm progress during discovery"),
        ("6", "dry_run", "Print commands without running them"),
    ]
    while True:
        sys.stdout.write(CLEAR_SCREEN if options.color else "\n")
        print(_color("Configuration", BOLD + CYAN, options))
        print()
        for key, attr, label in toggles:
            value = getattr(options, attr)
            state = "ON" if value else "OFF"
            print(f"{key}. {label:<52} {state}")
        print()
        print("Press 1-6 to toggle, q to return.")
        try:
            key = _read_key()
        except NoTTY:
            return
        if key in {"q", "Q", "esc"}:
            return
        for toggle_key, attr, _label in toggles:
            if key == toggle_key:
                setattr(options, attr, not getattr(options, attr))
                break


def run_interactive(
    title: str,
    config: LauncherConfig,
    repo_root: Path,
    options: RuntimeOptions,
) -> int:
    sections, items = build_menu_items(config, repo_root, options)
    grouped = _group_by_section(sections, items)
    section_index = 0
    item_index = 0
    status = ""
    _enter_alt_screen(options)
    alt_screen_active = True
    try:
        while True:
            current_items = grouped.get(sections[section_index].id, [])
            if current_items:
                item_index = min(item_index, len(current_items) - 1)
            else:
                item_index = 0
            _render_main(title, sections, grouped, section_index,
                         item_index, options, status)
            status = ""
            try:
                key = _read_key()
            except NoTTY:
                _leave_alt_screen(options)
                alt_screen_active = False
                return run_numeric(title, sections, grouped, repo_root, options)
            except KeyboardInterrupt:
                return 0
            if key in {"q", "Q", "esc"}:
                return 0
            if key == "up" and current_items:
                item_index = (item_index - 1) % len(current_items)
            elif key == "down" and current_items:
                item_index = (item_index + 1) % len(current_items)
            elif key == "left":
                section_index = (section_index - 1) % len(sections)
                item_index = 0
            elif key == "right":
                section_index = (section_index + 1) % len(sections)
                item_index = 0
            elif key == "home":
                item_index = 0
            elif key == "end" and current_items:
                item_index = len(current_items) - 1
            elif key in {"c", "C"}:
                _render_config(options)
            elif key in {"r", "R"}:
                sections, items = build_menu_items(config, repo_root, options)
                grouped = _group_by_section(sections, items)
                status = _color("Refreshed discovered scripts.", GREEN, options)
            elif key == "enter" and current_items:
                item = current_items[item_index]
                _leave_alt_screen(options)
                alt_screen_active = False
                rc = run_script(item, repo_root, options)
                status = _color("Done.", GREEN, options) if rc == 0 else _color(
                    f"Exit code {rc}.", RED, options)
                _enter_alt_screen(options)
                alt_screen_active = True
    finally:
        if alt_screen_active:
            _leave_alt_screen(options)


def _flat_items(sections: tuple[Section, ...], grouped: dict[str, list[ScriptItem]]) -> list[ScriptItem]:
    flat: list[ScriptItem] = []
    for section in sections:
        flat.extend(grouped.get(section.id, []))
    return flat


def print_list(
    title: str,
    sections: tuple[Section, ...],
    grouped: dict[str, list[ScriptItem]],
    *,
    show_numbers: bool = False,
) -> None:
    print(title)
    print("=" * len(title))
    item_number = 1
    for section in sections:
        section_items = grouped.get(section.id, [])
        if not section_items:
            continue
        print()
        print(section.title)
        for item in section_items:
            marker = " [discovered]" if item.discovered else ""
            prefix = f"{item_number:>3}. " if show_numbers else "  "
            print(f"{prefix}{item.id:<45} {item.label}{marker}")
            print(f"    {item.description}")
            item_number += 1


def run_numeric(
    title: str,
    sections: tuple[Section, ...],
    grouped: dict[str, list[ScriptItem]],
    repo_root: Path,
    options: RuntimeOptions,
) -> int:
    items = _flat_items(sections, grouped)
    if not sys.stdin.isatty():
        print_list(title, sections, grouped)
        return 0
    while True:
        print_list(title, sections, grouped, show_numbers=True)
        print("\n0. Exit")
        choice = input("Choice number or script id: ").strip()
        if choice in {"0", "q", "quit", "exit"}:
            return 0
        selected: ScriptItem | None = None
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(items):
                selected = items[index]
        else:
            selected = next((item for item in items if item.id == choice), None)
        if selected is None:
            print("Unknown choice.")
            continue
        run_script(selected, repo_root, options)


def _options_from_config(config: LauncherConfig, args: argparse.Namespace) -> RuntimeOptions:
    options = RuntimeOptions(
        wait_after_run=config.defaults.get("wait_after_run", True),
        confirm_before_run=config.defaults.get("confirm_before_run", True),
        show_discovered=config.defaults.get("show_discovered", True),
        color=config.defaults.get("color", True),
        progress=config.defaults.get("progress", True),
        dry_run=False,
    )
    if args.dry_run:
        options.dry_run = True
    if args.no_color:
        options.color = False
    if args.no_discovery:
        options.show_discovered = False
    if args.no_progress or args.list or args.run:
        options.progress = False
    if args.yes:
        options.confirm_before_run = False
    return options


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive project script launcher")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG),
                        help="YAML script catalog")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Project root")
    parser.add_argument("--numeric", action="store_true", help="Use numbered fallback UI")
    parser.add_argument("--list", action="store_true", help="List scripts and exit")
    parser.add_argument("--run", help="Run a script by id")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print command without executing")
    parser.add_argument("--yes", action="store_true",
                        help="Do not ask for run confirmation")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    parser.add_argument("--no-discovery", action="store_true",
                        help="Only show YAML scripts")
    parser.add_argument("--no-progress", action="store_true",
                        help="Disable tqdm discovery progress")
    parser.add_argument("--log-level", default="INFO", help="Python logging level")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        format="%(asctime)s %(levelname).4s: %(message)s",
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
    )
    config_path = Path(args.config).resolve()
    repo_root = Path(args.repo_root).resolve()
    config = load_config(config_path)
    options = _options_from_config(config, args)
    if options.color and not _enable_ansi_on_windows():
        options.color = False
    sections, items = build_menu_items(config, repo_root, options)
    grouped = _group_by_section(sections, items)
    if args.list:
        print_list(config.title, sections, grouped)
        return 0
    if args.run:
        item = next((candidate for candidate in items if candidate.id == args.run), None)
        if item is None:
            _logger.error("unknown script id: %s", args.run)
            return 2
        return run_script(item, repo_root, options)
    if args.numeric or not sys.stdin.isatty():
        return run_numeric(config.title, sections, grouped, repo_root, options)
    return run_interactive(config.title, config, repo_root, options)


if __name__ == "__main__":
    sys.exit(main())
