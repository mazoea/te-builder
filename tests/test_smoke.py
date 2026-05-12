"""Sentinel test so CI has something to pass until the real tests land."""

from __future__ import annotations

import importlib


def test_te_builder_package_imports() -> None:
    module = importlib.import_module("te_builder")
    assert module.__version__
