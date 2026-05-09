"""Manifest dispatch tests for tools/cad/render.py.

Pure-function tests — no build123d, no filesystem. Verifies the manifest
filtering logic that decides which parts get rendered.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

CAD_DIR = Path(__file__).resolve().parents[3] / "tools" / "cad"


def _import_render():
    """Import tools/cad/render.py without it being a package."""
    spec = importlib.util.spec_from_file_location("render", CAD_DIR / "render.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render = _import_render()


def test_filter_active_drops_deferred():
    parts = [
        {"name": "a", "status": "active"},
        {"name": "b", "status": "deferred"},
        {"name": "c", "status": "planned"},
        {"name": "d", "status": "active"},
    ]
    kept = render.filter_active(parts)
    assert [p["name"] for p in kept] == ["a", "d"]


def test_filter_active_keeps_unspecified_status():
    """Parts without an explicit status are treated as active."""
    parts = [{"name": "x"}, {"name": "y", "status": "active"}]
    kept = render.filter_active(parts)
    assert {p["name"] for p in kept} == {"x", "y"}


def test_filter_active_returns_empty_when_all_deferred():
    parts = [{"name": "z", "status": "deferred"}]
    assert render.filter_active(parts) == []


def test_manifest_is_valid_json_with_required_keys():
    """Real parts.json should parse and every entry should have the keys
    render.py's dispatcher uses."""
    parts = render.load_manifest()
    assert isinstance(parts, list) and parts
    required = {"name", "cad", "build_func", "stl", "svg", "status"}
    for part in parts:
        missing = required - part.keys()
        assert not missing, f"{part.get('name', '?')} missing keys: {missing}"
