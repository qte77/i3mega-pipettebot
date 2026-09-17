"""Tests for tools/motion_profile_plot.py.

Two layers: (1) the closed-form trapezoidal/triangular kinematics math,
which is real logic worth testing directly against known values, and
(2) a smoke test that the script runs end-to-end and produces the
three SVG files (rendering/wiring itself is not exhaustively tested —
per this repo's testing philosophy, rendering = e2e is the test).

Marked `viz`: requires matplotlib (`uv sync --extra viz`); skipped
otherwise, mirroring `tests/tools/cad/test_parts_smoke.py`'s `cad`
marker + `pytest.importorskip("build123d")` pattern.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.viz

matplotlib = pytest.importorskip("matplotlib")

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_motion_profile_plot():
    path = TOOLS_DIR / "motion_profile_plot.py"
    spec = importlib.util.spec_from_file_location("motion_profile_plot", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    # Register before exec: the module defines frozen dataclasses with
    # postponed (`from __future__ import annotations`) type hints, and
    # `dataclasses` resolves those via `sys.modules[cls.__module__]` — an
    # unregistered dynamic module makes that lookup return None and crash.
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mpp = _import_motion_profile_plot()


class TestAxisKinematics:
    """Closed-form trapezoidal/triangular single-axis move kinematics."""

    def test_trapezoidal_known_values(self) -> None:
        # D=100mm, feed=10mm/s, accel=5mm/s^2, no jerk -> textbook trapezoid.
        k = mpp.axis_kinematics(
            distance_mm=100.0, feed_mm_s=10.0, accel_mm_s2=5.0, jerk_mm_s=0.0
        )
        assert k.is_trapezoidal is True
        assert k.v_peak == pytest.approx(10.0)
        assert k.t_ramp == pytest.approx(2.0)
        assert k.t_cruise == pytest.approx(8.0)
        assert k.t_total == pytest.approx(12.0)

    def test_triangular_known_values(self) -> None:
        # D=10mm is too short to reach the 10mm/s feed cap at 5mm/s^2 accel.
        k = mpp.axis_kinematics(
            distance_mm=10.0, feed_mm_s=10.0, accel_mm_s2=5.0, jerk_mm_s=0.0
        )
        assert k.is_trapezoidal is False
        assert k.v_peak == pytest.approx(math.sqrt(50.0))
        assert k.t_cruise == pytest.approx(0.0)
        assert k.t_total == pytest.approx(2 * math.sqrt(50.0) / 5.0)

    def test_jerk_offsets_ramp_without_changing_total_distance(self) -> None:
        k = mpp.axis_kinematics(
            distance_mm=100.0, feed_mm_s=10.0, accel_mm_s2=5.0, jerk_mm_s=2.0
        )
        assert k.is_trapezoidal is True
        assert k.t_ramp == pytest.approx((10.0 - 2.0) / 5.0)
        d_ramp_each = (k.v_peak**2 - 2.0**2) / (2 * 5.0)
        assert (2 * d_ramp_each + k.d_cruise) == pytest.approx(100.0)

    def test_jerk_clamped_to_feed(self) -> None:
        # A jerk value above the feed cap must not produce v_peak < jerk.
        k = mpp.axis_kinematics(
            distance_mm=100.0, feed_mm_s=1.0, accel_mm_s2=5.0, jerk_mm_s=50.0
        )
        assert k.jerk_mm_s <= k.feed_mm_s

    @pytest.mark.parametrize("axis", ["x", "y", "z"])
    def test_faster_profile_ramps_up_quicker(self, axis: str) -> None:
        """Acceptance criterion: switching MOTION_PROFILE visibly changes traces.

        Uses a distance long enough that every bundled profile reaches its
        feedrate cap (trapezoidal), isolating the ramp-time comparison to
        the accel/jerk difference between SLOW/MID/FAST.
        """
        from pipettebot.motion_profile import FAST, MID, SLOW

        distance_mm = 2000.0
        ramps = []
        for profile in (SLOW, MID, FAST):
            k = mpp.axis_kinematics(
                distance_mm=distance_mm,
                feed_mm_s=getattr(profile, f"feed_{axis}"),
                accel_mm_s2=getattr(profile, f"accel_{axis}"),
                jerk_mm_s=getattr(profile, f"jerk_{axis}"),
            )
            assert k.is_trapezoidal, f"expected trapezoidal for {profile.name}/{axis}"
            ramps.append(k.t_ramp)
        assert ramps[2] < ramps[1] < ramps[0]  # FAST < MID < SLOW ramp time


class TestRenderAll:
    """Smoke test: the script runs and produces the three SVG files."""

    def test_renders_three_svgs(self, tmp_path: Path) -> None:
        from pipettebot.motion_profile import MID

        out_paths = mpp.render_all(MID, tmp_path)
        assert len(out_paths) == 3
        for p in out_paths:
            assert p.exists()
            assert p.suffix == ".svg"
            assert "<svg" in p.read_text()

    def test_different_profiles_change_peak_ramp_time(self) -> None:
        """Numeric proxy for 'visibly different traces' between profiles."""
        from pipettebot.motion_profile import FAST, SLOW

        slow_k = mpp.axis_kinematics(
            distance_mm=2000.0,
            feed_mm_s=SLOW.feed_x,
            accel_mm_s2=SLOW.accel_x,
            jerk_mm_s=SLOW.jerk_x,
        )
        fast_k = mpp.axis_kinematics(
            distance_mm=2000.0,
            feed_mm_s=FAST.feed_x,
            accel_mm_s2=FAST.accel_x,
            jerk_mm_s=FAST.jerk_x,
        )
        assert fast_k.t_ramp < slow_k.t_ramp
