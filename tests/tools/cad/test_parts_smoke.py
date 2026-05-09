"""Smoke tests for copied so101 CAD scripts.

Each `build_*()` returns a non-empty build123d shape. Marked `cad`:
requires build123d (`uv sync --extra cad`); skipped otherwise.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.cad

CAD_DIR = Path(__file__).resolve().parents[3] / "tools" / "cad"

build123d = pytest.importorskip("build123d")


def _import(rel: str):
    """Import a tools/cad/<rel>.py module, mimicking render.py's loader."""
    path = CAD_DIR / rel
    sys.path.insert(0, str(path.parent.parent))  # tools/cad/ on path for util.export
    try:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


def _is_non_empty_shape(shape) -> bool:
    return isinstance(shape, (build123d.Solid, build123d.Compound)) and shape.volume > 0


@pytest.mark.parametrize(
    ("rel", "func"),
    [
        ("labware/tip_rack_holder.py", "build_tip_rack_holder"),
        ("labware/plate_holder.py", "build_plate_holder"),
        ("dpette/tip_ejection_bar.py", "build_tip_ejection_bar"),
        ("dpette/dpette_cradle.py", "build_dpette_single_cradle"),
        ("dpette/dpette_cradle.py", "build_dpette_multi_cradle"),
        ("dpette/dpette_tip_release.py", "build_tip_release"),
    ],
)
def test_build_func_returns_non_empty_shape(rel: str, func: str):
    mod = _import(rel)
    shape = getattr(mod, func)()
    assert _is_non_empty_shape(shape), f"{rel}::{func} returned empty/non-shape"
