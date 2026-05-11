"""Hypothesis-style tests for tools/cad/i3/carriage_dpette_mount.py.

Asserts the AI3M payload budget (mount + pipette + tips < 300 g) and
geometric invariants. Marker `cad` — requires build123d
(`uv sync --extra cad`); skipped otherwise.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.cad

build123d = pytest.importorskip("build123d")

CAD_DIR = Path(__file__).resolve().parents[4] / "tools" / "cad"


def _import_mount():
    """Import the mount module mimicking render.py's loader."""
    sys.path.insert(0, str(CAD_DIR))
    try:
        spec = importlib.util.spec_from_file_location(
            "carriage_dpette_mount", CAD_DIR / "i3" / "carriage_dpette_mount.py"
        )
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


mount = _import_mount()


# === System-mass constants for the budget assertion ===
PIPETTE_MASS_G = 250.0  # dPette+ 8-channel, measured
TIPS_MASS_G = 3.0  # 8 × 300 µL polypropylene tips
AI3M_PAYLOAD_CAP_G = 300.0  # empirical AI3M direct-drive carriage limit


def _estimated_mass_g(shape) -> float:
    """Estimate PLA mass from a build123d shape's volume."""
    volume_cc = shape.volume / 1000.0  # mm³ → cc
    return volume_cc * mount.PLA_DENSITY_G_PER_CC


def test_main_returns_non_empty_shape():
    shape = mount.build_carriage_dpette_mount_main()
    assert isinstance(shape, (build123d.Solid, build123d.Compound))
    assert shape.volume > 0


def test_cap_returns_non_empty_shape():
    shape = mount.build_carriage_dpette_mount_cap()
    assert isinstance(shape, (build123d.Solid, build123d.Compound))
    assert shape.volume > 0


def test_payload_budget_under_300g():
    """Main + cap + pipette + tips must fit under the AI3M payload cap."""
    main_mass = _estimated_mass_g(mount.build_carriage_dpette_mount_main())
    cap_mass = _estimated_mass_g(mount.build_carriage_dpette_mount_cap())
    total = main_mass + cap_mass + PIPETTE_MASS_G + TIPS_MASS_G
    assert total < AI3M_PAYLOAD_CAP_G, (
        f"Total payload {total:.1f} g exceeds {AI3M_PAYLOAD_CAP_G} g cap "
        f"(main={main_mass:.1f} g + cap={cap_mass:.1f} g + "
        f"pipette={PIPETTE_MASS_G} g + tips={TIPS_MASS_G} g)"
    )


def test_main_height_within_z_envelope():
    """Main piece height must keep the lower clamp within reach of the bed."""
    shape = mount.build_carriage_dpette_mount_main()
    bbox = shape.bounding_box()
    height = bbox.size.Z
    assert height < 75, f"Mount main is {height:.1f} mm tall — exceeds Z envelope"


def test_cap_height_matches_top_plate():
    """Cap thickness in Z must equal the top-plate thickness (matched mating)."""
    cap = mount.build_carriage_dpette_mount_cap()
    bbox = cap.bounding_box()
    z_extent = bbox.size.Z
    assert abs(z_extent - mount.TOP_PLATE_T_MM) < 0.5, (
        f"Cap Z-extent {z_extent:.2f} doesn't match top-plate {mount.TOP_PLATE_T_MM}"
    )


def test_upper_clamp_height_fits_within_round_barrel():
    """Top plate (= upper clamp ring height) must be ≤ Ø27 round barrel height."""
    assert mount.TOP_PLATE_T_MM <= mount.UPPER_BARREL_HEIGHT_MM, (
        f"Upper clamp ring is {mount.TOP_PLATE_T_MM} mm tall but the "
        f"Ø27 round section is only {mount.UPPER_BARREL_HEIGHT_MM} mm — "
        "clamp would grip on the wider transition zones above/below."
    )


def test_main_x_symmetric():
    """Main piece is X-symmetric about the post axis."""
    shape = mount.build_carriage_dpette_mount_main()
    bbox = shape.bounding_box()
    assert abs(bbox.min.X + bbox.max.X) < 0.5, (
        f"Main is not X-symmetric: bbox X = [{bbox.min.X:.2f}, {bbox.max.X:.2f}]"
    )


def test_cap_x_symmetric():
    """Cap is X-symmetric about the bore axis."""
    shape = mount.build_carriage_dpette_mount_cap()
    bbox = shape.bounding_box()
    assert abs(bbox.min.X + bbox.max.X) < 0.5, (
        f"Cap is not X-symmetric: bbox X = [{bbox.min.X:.2f}, {bbox.max.X:.2f}]"
    )


# === Scheme b — L-bracket reinforcement variant ===


def test_lbracket_returns_non_empty_shape():
    shape = mount.build_carriage_dpette_mount_main_lbracket()
    assert isinstance(shape, (build123d.Solid, build123d.Compound))
    assert shape.volume > 0


def test_lbracket_volume_exceeds_main():
    """Scheme b adds material above scheme a — must be heavier."""
    main_vol = mount.build_carriage_dpette_mount_main().volume
    lbracket_vol = mount.build_carriage_dpette_mount_main_lbracket().volume
    assert lbracket_vol > main_vol, (
        f"Scheme b ({lbracket_vol:.0f} mm³) must exceed scheme a ({main_vol:.0f} mm³)"
    )


def test_lbracket_payload_budget_under_300g():
    """Scheme b + cap + pipette + tips must fit under the AI3M payload cap."""
    main_mass = _estimated_mass_g(mount.build_carriage_dpette_mount_main_lbracket())
    cap_mass = _estimated_mass_g(mount.build_carriage_dpette_mount_cap())
    total = main_mass + cap_mass + PIPETTE_MASS_G + TIPS_MASS_G
    assert total < AI3M_PAYLOAD_CAP_G, (
        f"Scheme b total payload {total:.1f} g exceeds {AI3M_PAYLOAD_CAP_G} g cap "
        f"(main_lbracket={main_mass:.1f} g + cap={cap_mass:.1f} g + "
        f"pipette={PIPETTE_MASS_G} g + tips={TIPS_MASS_G} g)"
    )


def test_lbracket_reaches_vplate_top_height():
    """L-bracket flange must reach the V-plate top-hole Z height."""
    shape = mount.build_carriage_dpette_mount_main_lbracket()
    bbox = shape.bounding_box()
    expected_top = mount.VPLATE_TOP_OFFSET_MM + mount.LBRACKET_FLANGE_T_MM
    assert abs(bbox.max.Z - expected_top) < 0.5, (
        f"Scheme b top Z = {bbox.max.Z:.2f}; expected ≈ {expected_top:.2f} "
        "(VPLATE_TOP_OFFSET_MM + LBRACKET_FLANGE_T_MM)"
    )


def test_lbracket_x_symmetric():
    """Scheme b is X-symmetric — flange and bolt holes both centred."""
    shape = mount.build_carriage_dpette_mount_main_lbracket()
    bbox = shape.bounding_box()
    assert abs(bbox.min.X + bbox.max.X) < 0.5, (
        f"Scheme b is not X-symmetric: bbox X = [{bbox.min.X:.2f}, {bbox.max.X:.2f}]"
    )


def test_lbracket_flange_clears_bolt_pitch():
    """Flange width must accommodate the bolt pitch with edge clearance."""
    edge_clear = (mount.LBRACKET_FLANGE_W_MM - mount.VPLATE_TOP_HOLE_PITCH_MM) / 2 - (
        mount.VPLATE_TOP_HOLE_D_MM / 2
    )
    assert edge_clear >= 1.5, (
        f"Bolt edge clearance {edge_clear:.2f} mm < 1.5 mm — widen flange"
    )
