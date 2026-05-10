"""Tests for tools/cad/dpette/tip_ejection_bar.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.cad

build123d = pytest.importorskip("build123d")

CAD_DIR = Path(__file__).resolve().parents[3] / "tools" / "cad"


def _import_module():
    sys.path.insert(0, str(CAD_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "tip_ejection_bar", CAD_DIR / "dpette" / "tip_ejection_bar.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


mod = _import_module()


def test_z_range_is_contiguous_from_base_bottom_to_cone_top():
    """Post sits on top of base; cone sits on top of post. No floating
    sections of geometry below the base or gaps between primitives."""
    shape = mod.build_tip_ejection_bar()
    bbox = shape.bounding_box()
    expected_min_z = -mod.BASE_THICKNESS / 2
    expected_max_z = mod.BASE_THICKNESS / 2 + mod.POST_HEIGHT + mod.POST_TIP_RADIUS * 2
    assert abs(bbox.min.Z - expected_min_z) < 0.01, (
        f"min Z = {bbox.min.Z:.2f}, expected {expected_min_z:.2f} "
        "(base bottom). Anything lower means a primitive is positioned "
        "below the base — likely a Pos(...) centre-vs-base bug."
    )
    assert abs(bbox.max.Z - expected_max_z) < 0.01, (
        f"max Z = {bbox.max.Z:.2f}, expected {expected_max_z:.2f} "
        "(cone top). Lower means primitives are overlapping; higher "
        "means there's a gap in the assembly."
    )


def test_part_is_x_y_symmetric_about_origin():
    """Base, post, and cone are all centred on (0, 0) by design."""
    shape = mod.build_tip_ejection_bar()
    bbox = shape.bounding_box()
    assert abs(bbox.min.X + bbox.max.X) < 0.01
    assert abs(bbox.min.Y + bbox.max.Y) < 0.01
