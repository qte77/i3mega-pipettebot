"""Tests for tools/cad/barrel_bore.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.cad

build123d = pytest.importorskip("build123d")

CAD_DIR = Path(__file__).resolve().parents[3] / "tools" / "cad"


def _import_barrel_bore():
    sys.path.insert(0, str(CAD_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "barrel_bore", CAD_DIR / "barrel_bore.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


barrel_bore = _import_barrel_bore()


def test_make_clamp_bore_returns_cylinder():
    bore = barrel_bore.make_clamp_bore(27.0, 8.0)
    assert isinstance(bore, build123d.Cylinder)
    assert bore.volume > 0


def test_make_clamp_bore_default_clearance_inflates_diameter_by_0p5():
    """Default 0.5 mm diametral clearance: bore Ø = nominal + 0.5."""
    bore = barrel_bore.make_clamp_bore(27.0, 8.0)
    bbox = bore.bounding_box()
    # Cylinder bbox X+Y are the diameter.
    assert abs(bbox.size.X - 27.5) < 1e-6
    assert abs(bbox.size.Y - 27.5) < 1e-6


def test_make_clamp_bore_explicit_clearance():
    """Cradle-style 1.0 mm diametral clearance: bore Ø = nominal + 1.0."""
    bore = barrel_bore.make_clamp_bore(20.0, 30.0, diametral_clearance_mm=1.0)
    bbox = bore.bounding_box()
    assert abs(bbox.size.X - 21.0) < 1e-6


def test_make_clamp_bore_height_matches():
    bore = barrel_bore.make_clamp_bore(27.0, 12.5)
    bbox = bore.bounding_box()
    assert abs(bbox.size.Z - 12.5) < 1e-6


def test_make_clamp_bore_axis_along_z():
    """Built cylinder is centred at origin with Z axis."""
    bore = barrel_bore.make_clamp_bore(27.0, 8.0)
    bbox = bore.bounding_box()
    assert abs(bbox.min.X + bbox.max.X) < 1e-6  # X-symmetric
    assert abs(bbox.min.Y + bbox.max.Y) < 1e-6  # Y-symmetric
    assert abs(bbox.min.Z + bbox.max.Z) < 1e-6  # Z-symmetric


def test_zero_clearance_returns_nominal_diameter():
    bore = barrel_bore.make_clamp_bore(20.0, 10.0, diametral_clearance_mm=0.0)
    bbox = bore.bounding_box()
    assert abs(bbox.size.X - 20.0) < 1e-6
