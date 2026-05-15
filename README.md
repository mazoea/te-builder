# te-builder

Builds the Mazoea text-extractor native dependency chain — zlib, libpng,
libtiff, jpeg, giflib, freetype, leptonica, tesseract, and friends — by
driving MSBuild, then copies the `.lib`/`.dll` outputs into
per-configuration directories.

## Prerequisites

- Python 3.11+
- MSBuild from Visual Studio 2017/2019/2022/2026 on `PATH` (auto-detected
  via `vswhere.exe`)
- `cmake` on `PATH` for the CMake-based presets (`leptonica`,
  `tesseract*`, `i2t`) — te-builder builds those through their own
  `cmaker.bat`

## Quickstart

```
git clone git@github.com:mazoea/te-builder.git
git clone git@github.com:mazoea/te-external.git
cd te-builder
python -m pip install -e ".[dev,launcher]"

scripts\startme.bat                          # interactive menu
python -m te_builder --preset externals.basic   # or call the CLI
```

## Presets

Common packaged presets (not exhaustive — run without `--preset` to list
them all):

| Preset | Builds | Requires |
|---|---|---|
| `externals.basic` | zlib, libtiff, libpng, jpeg, giflib, freetype | `te-external/` |
| `externals` | basic + libffi, libiconv, libxml2, icu, fontconfig, glib, harfbuzz, pixman, cairo, pango | `te-external/` |
| `leptonica` | leptonica | `te-external-leptonica/` |
| `tesseract3` | tesseract 3 | `te-external-tesseract/tesseract/` |
| `tesseract3-all` | basic externals + leptonica + tesseract 3 | all of the above |
| `tesseract4` | tesseract 4 | `te-external-tesseract4/tesseract/` |

Pass a path to `--preset` instead of a name to use a custom JSON file, or
repeat `--preset` to merge several left-to-right — later presets override
earlier ones, so a config-only overlay like `minimal_configurations`
composes onto a project preset:

```
python -m te_builder --preset externals.basic --preset minimal_configurations
```

The CMake-based projects (`leptonica`, `tesseract*`, `i2t`) ship no
committed `.sln`. te-builder detects their `cmaker.bat` and runs it to
configure and build the project in one shot. The hand-curated
`te-external` libraries have committed `.sln` files and are built per
configuration through MSBuild.

## Configurations

Default: `Debug-MTDLL|x64`, `Release-MTDLL|x64` — the configurations the
hand-curated `te-external` image-lib solutions declare. Override with
`--configurations` or a `"configurations"` key in the preset JSON. These
apply only to the MSBuild-driven `te-external` projects; the CMake-based
projects build whatever their `cmaker.bat` declares.

Outputs land in `<project>/libs/<configuration>/` so configurations don't
overwrite each other.

## Toolset detection

Without `--msvc-toolset`, te-builder runs `vswhere.exe` and maps each VS
install to its platform toolset (VS 2017 → `v141`, 2019 → `v142`,
2022 → `v143`, 2026 → `v145`). One install is used silently; with several,
you're prompted on a TTY (newest is the default) or the newest wins on CI.

Run `scripts\list-vs.bat` to see the list without building.

## CLI

```
python -m te_builder --help
```

- `--preset NAME_OR_PATH` — packaged preset name or path to a custom JSON;
  repeat to merge several left-to-right
- `--project-root PATH` — parent directory of the sibling repos
- `--msvc-toolset v143` — MSVC toolset (default: auto-detect)
- `--configurations Release|x64 Debug-MTDLL|x64` — override the preset
- `--dry-run` — print the plan without invoking MSBuild
- `--log-level DEBUG|INFO|WARNING|ERROR` — default `INFO`

Running without `--preset` lists the available presets and exits.

## License

MIT. See [LICENSE](LICENSE).
