"""Backwards-compatible re-export.

The legacy `settings.settings` dict has been replaced by `te_builder.Env`.
Keeping this shim around lets older imports (`from settings import settings`)
keep working long enough for downstream tooling to migrate.
"""

from __future__ import annotations

from te_builder.config import Env

settings = Env.defaults()
