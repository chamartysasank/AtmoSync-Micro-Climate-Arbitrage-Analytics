"""View registry. Every module in this package that defines TITLE, ORDER and render(ctx) becomes a navigation entry.
Adding a feature page = adding one file here (no edits to streamlit_app.py)."""
from __future__ import annotations
import importlib, pkgutil


def discover() -> list:
    views = []
    for info in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(f"{__name__}.{info.name}")
        if all(hasattr(mod, a) for a in ("TITLE", "ORDER", "render")):
            views.append(mod)
    return sorted(views, key=lambda m: m.ORDER)
