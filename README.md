# te-builder

Build orchestrator for the Mazoea text-extractor native dependency chain.
Drives MSBuild (or a `cmaker.bat` script provided by the upstream repo)
across a curated list of C/C++ libraries — zlib, libpng, libtiff, jpeg,
giflib, freetype, leptonica, tesseract, optionally cairo / pango / glib /
icu — and copies the resulting `.lib` / `.dll` outputs into per-configuration
directories so consumers can pick the right flavour.

## Repository layout (required)

te-builder assumes a set of sibling git checkouts under the same parent
directory. The packaged presets reference these paths relative to
`projects_top_dir = ../..` of the `te_builder` package:

```
parent/
├─ te-builder/                  # this repo
├─ te-external/                 # zlib, libpng, libtiff, jpeg, giflib, freetype, …
├─ te-external-leptonica/       # leptonica (private)
├─ te-external-tesseract/       # tesseract 3 (private)
├─ te-external-tesseract4/      # tesseract 4 (private)
└─ c++image-to-text/            # i2t.json preset (private)
```

Override the parent directory with `--project-root /path/to/parent` if your
checkouts live somewhere else.

## Prerequisites

- Python 3.11 or newer.
- MSBuild from Visual Studio 2019 or 2022 on `PATH`. The default toolset is
  `v143` (VS 2022); pass `--msvc-toolset v142` for VS 2019.
- Optional: `cmake` for projects that ship a `cmaker.bat`.
- Optional: `pre-commit` if you want the bundled autopep8 hook.

## Quickstart

```
git clone git@github.com:mazoea/te-builder.git
git clone git@github.com:mazoea/te-external.git
cd te-builder

# editable install with dev (pytest, ruff) and launcher (PyYAML, tqdm) extras
python -m pip install -e ".[dev,launcher]"

# interactive menu
scripts\startme.bat

# or call the CLI directly
python -m te_builder --preset externals.basic
```

## Preset matrix

| Preset | Builds | Requires |
|---|---|---|
| `externals.basic` | zlib, libtiff, libpng, jpeg, giflib, freetype | `te-external/` |
| `externals` | basic + libffi, libiconv, libxml2, icu, fontconfig, glib, harfbuzz, pixman, cairo, pango | `te-external/` |
| `externals.freetype` | zlib, libpng, freetype | `te-external/` |
| `externals.libpng` | libpng | `te-external/` |
| `leptonica` | leptonica | `te-external-leptonica/` |
| `tesseract3` | tesseract 3 | `te-external-tesseract/tesseract/` |
| `tesseract3_leptonica` | leptonica + tesseract 3 | `te-external-leptonica/`, `te-external-tesseract/tesseract/` |
| `tesseract3-all` | basic externals + leptonica + tesseract 3 | all of the above |
| `tesseract4` | tesseract 4 | `te-external-tesseract4/` |
| `i2t` | c++image-to-text | `c++image-to-text/` |
| `minimal_configurations` | configurations override only (no projects) | — |

Pass an absolute or relative path to `--preset` instead of a name to use a
custom JSON file.

## Configurations

Default configurations (in order):

1. `Release|x64`
2. `RelWithDebInfo|x64`
3. `Debug-MTDLL|x64`
4. `Release-MTDLL|x64`

Override with `--configurations Release|x64 Debug-MTDLL|x64` or by setting
`"configurations": [...]` in the preset JSON.

Build artifacts land in
`<project>/libs/<configuration>/*.{lib,dll,exp}` so multiple configurations
coexist without overwriting each other.

## CLI reference

```
python -m te_builder --help
```

Highlights:

- `--preset NAME_OR_PATH` — packaged preset name (no extension) or a path
  to a custom JSON.
- `--project-root PATH` — override the sibling-repo parent directory.
- `--msvc-toolset v143` — MSVC toolset; default is `v143`.
- `--configurations Release|x64 Debug-MTDLL|x64` — override the preset's
  configurations.
- `--dry-run` — print the plan without invoking MSBuild.
- `--log-level DEBUG|INFO|WARNING|ERROR` — default `INFO`.

Running without `--preset` prints the available presets and exits 2.

## Interactive launcher

`scripts\startme.bat` opens the bundled YAML-driven menu. Arrow keys
navigate, Enter runs the selected entry. The launcher is the recommended
day-to-day entry point: it exposes every preset, plus pytest, ruff check,
ruff format, and the editable install.

## Development

```
python -m pip install -e ".[dev,launcher]"
python -m pytest                       # or: scripts\pytest.bat
python -m ruff check src tests tools   # or: scripts\ruff-check.bat
python -m ruff format src tests tools  # or: scripts\ruff-format.bat
```

CI (GitHub Actions, `.github/workflows/ci.yml`) runs ruff + pytest on
ubuntu-latest and windows-latest, plus a Windows smoke job that clones
the public `te-external` repo and exercises `python -m te_builder
--preset externals.basic --dry-run`.

## Breaking changes vs. legacy `main.py`

- **`libs/<configuration>/`** namespacing replaces the shared `libs/`
  directory. Consumers that read `libs/*.lib` directly need to update.
- **`--preset NAME`** replaces `--settings=path/to/file.json`. Pass a path
  to use a custom preset instead.
- The undocumented `--settings=key=value` magic fallback has been removed.
- The interactive numbered menu has been removed; use `scripts\startme.bat`
  or pass `--preset` explicitly.
- Python 2 support is dropped; Python 3.11+ required.
- `vcrun.exit.bat` is gone; `vcrun.bat` is now a one-line msbuild wrapper.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).
