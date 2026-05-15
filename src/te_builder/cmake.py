"""cmake batch script discovery."""

from __future__ import annotations

from pathlib import Path


def discover_cmaker(project_dir: Path, batch_name: str) -> Path | None:
    """Locate the project's cmaker.bat.

    Two layouts are in use: c-image-to-text keeps cmaker.bat in the cmake
    project directory itself, while the te-external-leptonica / -tesseract
    repos keep it one level up, beside the project subdirectory it cd's
    into. Check the project directory first, then its parent.
    """
    for base in (project_dir, project_dir.parent):
        candidate = base / batch_name
        if candidate.is_file():
            return candidate
    return None
