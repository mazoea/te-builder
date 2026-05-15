"""Backwards-compatible re-export — read-only.

The legacy `settings.settings` was a plain `dict`. It is now an `Env`
dataclass instance from `te_builder.config`. This means
`from settings import settings` still resolves to *something*, but
dict-style access (`settings["log_dir"]`) and mutation will fail. Existing
imports should migrate to `te_builder.config.Env`. This shim exists so the
module import itself does not break overnight; it is not a compatibility
layer for the old dict interface.
"""

from __future__ import annotations

from te_builder.config import Env

settings = Env.defaults()
