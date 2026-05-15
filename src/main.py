"""Backwards-compatible shim for `python src/main.py ...`.

The real CLI lives in `te_builder.cli`. Prefer `python -m te_builder` or
the installed `te-builder` console script. This shim preserves the
historical entry point only — the legacy flag surface (`--settings=...`,
the interactive numbered menu, the `--settings=key=value` magic) is gone,
so existing invocations need to be rewritten with the new flags
(`--preset NAME`, `--project-root`, …). See README.md "Breaking changes".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from te_builder.cli import main  # noqa: E402  -- after sys.path adjustment

if __name__ == "__main__":
    sys.exit(main())
