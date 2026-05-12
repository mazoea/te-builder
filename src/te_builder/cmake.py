"""cmake batch script discovery."""

from __future__ import annotations

from pathlib import Path


def discover_cmaker(project_dir: Path, batch_name: str) -> Path | None:
    candidate = project_dir / batch_name
    return candidate if candidate.is_file() else None
