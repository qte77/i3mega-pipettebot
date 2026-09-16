"""Render motion-profile kinematics + deck-layout SVGs. No hardware needed.

Design-review visualization for the bundled `MotionProfile` (SLOW / MID /
FAST) in `pipettebot.motion_profile` and the row-tour deck geometry
hand-encoded in `examples/showcase_v0_i3_full_pipettebot_rows.py`.

Simulates a trapezoidal (or triangular, for moves too short to reach the
feedrate cap) velocity profile per axis via closed-form kinematics under
the M203 (feedrate), M201 (accel), and M205 (classic jerk) constraints
already bundled in `motion_profile.py` — no numerical integrator.

Jerk is rendered as a genuine instantaneous velocity step (not merely an
annotation): the closed-form ramp starts at v=jerk (not v=0) and ends by
dropping from v=jerk to 0, matching
`docs/sketches/motion-profile-graphs.md`'s "Jerk shown as instantaneous
v steps at junctions." At the jerk magnitudes bundled here (<=15 mm/s
against a 500 mm/s feed cap) this barely perturbs the physics — it is
mostly a visual acknowledgement of the sketch's spec.

Renders three SVGs to `hardware/svg/motion-profile/` (gitignored, same
convention as the CAD pipeline's `hardware/{stl,svg}/` output):

    1. kinematics_per_axis.svg   — 3-panel velocity/accel trapezoid, X/Y/Z
    2. three_view_path.svg       — top (X-Y) + side (X-Z) + side (Y-Z)
    3. deck_layout_top_view.svg  — replaces the ASCII sketch in
                                    docs/sketches/deck-layout-rows-script.md

Usage::

    MOTION_PROFILE=fast uv run tools/motion_profile_plot.py
    make render_motion_profile MOTION_PROFILE=mid

Deck-layout geometry (tip-box rows, reservoir, well rows, release bar,
home/park) is read from the row-tour showcase script via reflection
(`importlib` + attribute access), so this plot can never silently drift
from what the gantry actually receives. The one number NOT sourced this
way is the bed footprint outline: no `BED_X`/`BED_Y` constant exists
anywhere in this repo. It is hand-encoded below from the header text of
`docs/sketches/deck-layout-rows-script.md` ("i3 Mega bed = 210 x 210 mm"
corrected to a 220 mm Y envelope), which matches issue #116's own
example constants — visual context only, not a motion-safety bound, and
unverified against the physical machine.

Known discrepancy (not resolved here — flagged for the repo owner): the
showcase script's live `RELEASE_BAR_Y = 220.0` (re-measured "after an
earlier value of Y=190 was found to miss the hook", per its own inline
comment) conflicts with `docs/sketches/deck-layout-rows-script.md`'s
"Discrepancies to verify" section, which claims the opposite correction
direction (220 -> 190). This tool uses the live source value (220), per
this repo's own claim-verification rule (current code over a doc that
may itself be stale).

Y-axis orientation: unlike a build123d CAD-tool top view (see
`.claude/rules/cad-script-conventions.md` — those tools render +Y
pointing away from the viewer, opposite Marlin's +Y-toward-operator
convention, so build123d assemblies need an explicit post-translation
mirror), a bare 2D matplotlib plot has no such built-in inversion:
Marlin Y plotted directly on the vertical axis already increases
upward, which is exactly `docs/sketches/deck-layout-rows-script.md`'s
own FRONT-at-top layout. No Y-mirror is applied here.
"""

from __future__ import annotations

import importlib.util
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from pipettebot.motion_profile import MotionProfile, select_profile

if TYPE_CHECKING:
    from types import ModuleType

    from matplotlib.axes import Axes

REPO_ROOT = Path(__file__).resolve().parents[1]
SHOWCASE_PATH = REPO_ROOT / "examples" / "showcase_v0_i3_full_pipettebot_rows.py"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "hardware" / "svg" / "motion-profile"

# Bed footprint outline for the deck-layout panel only (visual context,
# NOT a motion-safety bound, NOT sourced from any in-repo constant — see
# module docstring). Verify against the physical bed before relying on it.
BED_X_MM = 210.0
BED_Y_MM = 220.0

_PHASE_COLORS = {
    "home": "#8b949e",
    "pickup": "#1f6feb",
    "aspirate": "#238636",
    "dispense": "#da3633",
    "eject": "#8957e5",
    "park": "#6e40c9",
}


# --- Closed-form single-axis kinematics ----------------------------------


@dataclass(frozen=True)
class AxisKinematics:
    """Closed-form trapezoidal (or triangular) move, start and end at rest.

    Jerk is modelled as an instantaneous velocity step at each end of the
    move (0 -> jerk at the start, jerk -> 0 at the end), matching Marlin's
    classic-jerk semantics for a lone move that starts and ends at rest.
    """

    distance_mm: float
    feed_mm_s: float
    accel_mm_s2: float
    jerk_mm_s: float
    v_peak: float
    t_ramp: float
    t_cruise: float
    t_total: float
    d_cruise: float
    is_trapezoidal: bool


def axis_kinematics(
    distance_mm: float, feed_mm_s: float, accel_mm_s2: float, jerk_mm_s: float
) -> AxisKinematics:
    """Compute the trapezoidal/triangular velocity profile for one axis move.

    Pure algebra, no numerical integration. `distance_mm` is the total
    move distance; `feed_mm_s` / `accel_mm_s2` / `jerk_mm_s` are the
    M203 / M201 / M205 caps for this axis.
    """
    jerk = min(jerk_mm_s, feed_mm_s) if feed_mm_s > 0 else 0.0
    ramp_distance = (feed_mm_s**2 - jerk**2) / accel_mm_s2
    if ramp_distance <= distance_mm:
        v_peak = feed_mm_s
        d_ramp_each = (v_peak**2 - jerk**2) / (2 * accel_mm_s2)
        d_cruise = distance_mm - 2 * d_ramp_each
        t_ramp = (v_peak - jerk) / accel_mm_s2
        t_cruise = d_cruise / v_peak if v_peak > 0 else 0.0
        is_trapezoidal = True
    else:
        v_peak = math.sqrt(accel_mm_s2 * distance_mm + jerk**2)
        d_cruise = 0.0
        t_ramp = (v_peak - jerk) / accel_mm_s2
        t_cruise = 0.0
        is_trapezoidal = False
    return AxisKinematics(
        distance_mm=distance_mm,
        feed_mm_s=feed_mm_s,
        accel_mm_s2=accel_mm_s2,
        jerk_mm_s=jerk,
        v_peak=v_peak,
        t_ramp=t_ramp,
        t_cruise=t_cruise,
        t_total=2 * t_ramp + t_cruise,
        d_cruise=d_cruise,
        is_trapezoidal=is_trapezoidal,
    )


def _velocity_points(k: AxisKinematics) -> tuple[list[float], list[float]]:
    """Piecewise-linear v(t) corner points, including the instant jerk steps."""
    t_cruise_end = k.t_ramp + k.t_cruise
    ts = [0.0, 0.0, k.t_ramp, t_cruise_end, k.t_total, k.t_total]
    vs = [0.0, k.jerk_mm_s, k.v_peak, k.v_peak, k.jerk_mm_s, 0.0]
    return ts, vs


def _accel_points(k: AxisKinematics) -> tuple[list[float], list[float]]:
    """Rectangular accel-pulse corner points (+a ramp-up, 0 cruise, -a ramp-down)."""
    t_cruise_end = k.t_ramp + k.t_cruise
    a = k.accel_mm_s2
    ts = [0.0, k.t_ramp, k.t_ramp, t_cruise_end, t_cruise_end, k.t_total]
    vs = [a, a, 0.0, 0.0, -a, -a]
    return ts, vs


# --- Reflection: read the row-tour showcase's own constants --------------


def _load_showcase() -> ModuleType:
    """Load the row-tour showcase script as a module (reflection, not execution).

    Safe: every constant/helper in that script lives at module scope, and
    all serial/motion side effects are gated behind `if __name__ ==
    "__main__":`. Mirrors the loader pattern in
    `tests/tools/test_preflight_cli.py` / `tests/tools/cad/test_parts_smoke.py`.
    """
    spec = importlib.util.spec_from_file_location("showcase_rows", SHOWCASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load spec for {SHOWCASE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # see motion_profile_plot's own loader note
    spec.loader.exec_module(mod)
    return mod


def _axis_spans(sc: ModuleType) -> dict[str, float]:
    """Representative per-axis move distance: the full X/Y/Z range the tour visits."""
    tip_ys = [sc._tip_box_y(n) for n in range(1, sc.MAX_NUM_CYCLES + 1)]
    well_ys = [sc._well_y(n) for n in range(1, sc.MAX_NUM_CYCLES + 1)]
    xs = [
        0.0,
        sc.TIP_BOX_X,
        sc.WELL_X,
        sc.RELEASE_APPROACH_X,
        sc.RELEASE_BAR_X,
        sc.PARK_FINAL_X,
        sc.PARK_CLEARANCE_X,
    ]
    ys = [
        0.0,
        sc.RESERVOIR_TRANSIT_Y,
        sc.RESERVOIR_Y,
        sc.PARK_FINAL_Y,
        sc.RELEASE_BAR_Y,
    ]
    ys += tip_ys + well_ys
    zs = [
        0.0,
        sc.POST_HOME_LIFT_Z,
        sc.TIP_BOX_APPROACH_Z,
        sc.TIP_PICKUP_Z,
        sc.TIP_BOX_CLEAR_Z,
        sc.RESERVOIR_DIVE_Z,
        sc.RESERVOIR_CLEAR_Z,
        sc.WELL_DISPENSE_Z,
        sc.WELL_CLEAR_Z,
        sc.RELEASE_ENGAGE_Z,
        sc.RELEASE_CLEAR_Z,
        sc.PARK_BELOW_BAR_Z,
        sc.PARK_INTERMEDIATE_Z,
    ]
    return {
        "x": max(xs) - min(xs),
        "y": max(ys) - min(ys),
        "z": max(zs) - min(zs),
    }


@dataclass(frozen=True)
class Waypoint:
    """One XYZ target on the reconstructed row-tour path, tagged by phase."""

    x: float
    y: float
    z: float
    phase: str


def _pickup_waypoints(sc: ModuleType, cycle: int) -> list[Waypoint]:
    y = sc._tip_box_y(cycle)
    return [
        Waypoint(sc.TIP_BOX_X, y, sc.TIP_BOX_APPROACH_Z, "pickup"),
        Waypoint(sc.TIP_BOX_X, y, sc.TIP_PICKUP_Z, "pickup"),
        Waypoint(sc.TIP_BOX_X, y, sc.TIP_BOX_CLEAR_Z, "pickup"),
    ]


def _aspirate_waypoints(sc: ModuleType) -> list[Waypoint]:
    x = sc.TIP_BOX_X  # X carries over from the tip box (per the showcase docstring)
    return [
        Waypoint(x, sc.RESERVOIR_TRANSIT_Y, sc.TIP_BOX_CLEAR_Z, "aspirate"),
        Waypoint(x, sc.RESERVOIR_Y, sc.RESERVOIR_DIVE_Z, "aspirate"),
        Waypoint(x, sc.RESERVOIR_Y, sc.RESERVOIR_CLEAR_Z, "aspirate"),
    ]


def _dispense_waypoints(sc: ModuleType, cycle: int) -> list[Waypoint]:
    y = sc._well_y(cycle)
    return [
        Waypoint(sc.WELL_X, y, sc.RESERVOIR_CLEAR_Z, "dispense"),
        Waypoint(sc.WELL_X, y, sc.WELL_DISPENSE_Z, "dispense"),
        Waypoint(sc.WELL_X, y, sc.WELL_CLEAR_Z, "dispense"),
    ]


def _eject_waypoints(sc: ModuleType) -> list[Waypoint]:
    return [
        Waypoint(sc.RELEASE_APPROACH_X, sc.RELEASE_BAR_Y, sc.WELL_CLEAR_Z, "eject"),
        Waypoint(sc.RELEASE_BAR_X, sc.RELEASE_BAR_Y, sc.WELL_CLEAR_Z, "eject"),
        Waypoint(sc.RELEASE_BAR_X, sc.RELEASE_BAR_Y, sc.RELEASE_ENGAGE_Z, "eject"),
        Waypoint(sc.RELEASE_BAR_X, sc.RELEASE_BAR_Y, sc.RELEASE_CLEAR_Z, "eject"),
    ]


def _park_waypoints(sc: ModuleType) -> list[Waypoint]:
    return [
        Waypoint(sc.PARK_CLEARANCE_X, sc.RELEASE_BAR_Y, sc.RELEASE_CLEAR_Z, "park"),
        Waypoint(sc.PARK_CLEARANCE_X, sc.RELEASE_BAR_Y, sc.PARK_INTERMEDIATE_Z, "park"),
        Waypoint(sc.PARK_FINAL_X, sc.PARK_FINAL_Y, sc.PARK_BELOW_BAR_Z, "park"),
    ]


def build_tour_waypoints(sc: ModuleType) -> list[Waypoint]:
    """Reconstruct the full row-tour path from the showcase's constants + helpers."""
    waypoints = [Waypoint(0.0, 0.0, sc.POST_HOME_LIFT_Z, "home")]
    for cycle in range(1, sc.MAX_NUM_CYCLES + 1):
        waypoints += _pickup_waypoints(sc, cycle)
        waypoints += _aspirate_waypoints(sc)
        waypoints += _dispense_waypoints(sc, cycle)
        waypoints += _eject_waypoints(sc)
    waypoints += _park_waypoints(sc)
    return waypoints


# --- Rendering -------------------------------------------------------------
# Figures are built directly from `matplotlib.figure.Figure` (no `pyplot`),
# so no GUI backend is ever resolved/imported — safe in a headless
# container with no DISPLAY. `Figure.savefig(..., format="svg")` picks the
# SVG writer regardless of which canvas (if any) is attached.


def _draw_kinematics_panel(ax: Axes, axis: str, k: AxisKinematics) -> None:
    t_v, v = _velocity_points(k)
    ax.plot(t_v, v, color="#1f6feb", linewidth=1.6, label="v [mm/s]")
    ax.set_xlabel("t [s]")
    ax.set_ylabel("v [mm/s]", color="#1f6feb")
    ax.set_title(f"{axis.upper()} axis")

    ax_accel = ax.twinx()
    t_a, a = _accel_points(k)
    ax_accel.plot(
        t_a, a, color="#da3633", linewidth=1.2, linestyle="--", label="a [mm/s²]"
    )
    ax_accel.set_ylabel("a [mm/s²]", color="#da3633")

    shape = (
        "trapezoid (cap reached)" if k.is_trapezoidal else "triangle (cap not reached)"
    )
    ax.annotate(
        f"v_peak={k.v_peak:.1f} mm/s\n{shape}\nd={k.distance_mm:.0f} mm",
        xy=(0.03, 0.95),
        xycoords="axes fraction",
        va="top",
        fontsize=8,
    )


def render_kinematics_svg(
    profile: MotionProfile, spans: dict[str, float], out_path: Path
) -> Path:
    """Render the 3-panel (X/Y/Z) kinematics-per-axis SVG."""
    fig = Figure(figsize=(13.0, 4.2), facecolor="white")
    axes = fig.subplots(1, 3)
    for ax, axis in zip(axes, ("x", "y", "z"), strict=True):
        ax.set_facecolor("white")
        k = axis_kinematics(
            distance_mm=spans[axis],
            feed_mm_s=getattr(profile, f"feed_{axis}"),
            accel_mm_s2=getattr(profile, f"accel_{axis}"),
            jerk_mm_s=getattr(profile, f"jerk_{axis}"),
        )
        _draw_kinematics_panel(ax, axis, k)
    fig.suptitle(f"Kinematics per axis — profile: {profile.name}")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.94))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg", facecolor=fig.get_facecolor())
    return out_path


def _draw_path_panel(
    ax: Axes,
    xs: list[float],
    ys: list[float],
    colors: list[str],
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    ax.set_facecolor("white")
    for i in range(len(xs) - 1):
        ax.plot(xs[i : i + 2], ys[i : i + 2], color=colors[i], linewidth=1.0)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_aspect("equal", adjustable="datalim")


def render_three_view_path_svg(sc: ModuleType, out_path: Path) -> Path:
    """Render the top (X-Y) + side (X-Z) + side (Y-Z) tour path SVG."""
    waypoints = build_tour_waypoints(sc)
    xs = [w.x for w in waypoints]
    ys = [w.y for w in waypoints]
    zs = [w.z for w in waypoints]
    colors = [_PHASE_COLORS.get(w.phase, "#8b949e") for w in waypoints]

    fig = Figure(figsize=(15.0, 5.2), facecolor="white")
    ax_top, ax_xz, ax_yz = fig.subplots(1, 3)
    _draw_path_panel(ax_top, xs, ys, colors, "Top view (X-Y)", "X [mm]", "Y [mm]")
    _draw_path_panel(ax_xz, xs, zs, colors, "Side (X-Z)", "X [mm]", "Z [mm]")
    _draw_path_panel(ax_yz, ys, zs, colors, "Side (Y-Z)", "Y [mm]", "Z [mm]")

    handles = [
        Line2D([0], [0], color=c, lw=2, label=p) for p, c in _PHASE_COLORS.items()
    ]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), fontsize=8)
    fig.suptitle(f"Three-view path plot — row tour ({sc.MAX_NUM_CYCLES} cycles)")
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.94))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg", facecolor=fig.get_facecolor())
    return out_path


def _scatter_group(
    ax: Axes, points: list[tuple[float, float]], color: str, label: str
) -> None:
    ax.scatter(
        [p[0] for p in points], [p[1] for p in points], color=color, label=label, s=36
    )


def render_deck_layout_svg(sc: ModuleType, out_path: Path) -> Path:
    """Render the deck-layout top view SVG (replaces the ASCII sketch)."""
    fig = Figure(figsize=(8.0, 8.4), facecolor="white")
    ax = fig.subplots(1, 1)
    ax.set_facecolor("white")

    ax.add_patch(
        Rectangle(
            (0.0, 0.0),
            BED_X_MM,
            BED_Y_MM,
            fill=False,
            edgecolor="#8b949e",
            linestyle="--",
        )
    )
    ax.annotate(
        "bed envelope (approx., unverified — see module docstring)",
        xy=(2.0, BED_Y_MM - 6.0),
        fontsize=7,
        color="#8b949e",
    )

    tip_rows = [
        (sc.TIP_BOX_X, sc._tip_box_y(n)) for n in range(1, sc.MAX_NUM_CYCLES + 1)
    ]
    well_rows = [(sc.WELL_X, sc._well_y(n)) for n in range(1, sc.MAX_NUM_CYCLES + 1)]

    _scatter_group(ax, tip_rows, _PHASE_COLORS["pickup"], "tip-box rows")
    _scatter_group(ax, well_rows, _PHASE_COLORS["dispense"], "96-well rows")
    _scatter_group(
        ax, [(sc.TIP_BOX_X, sc.RESERVOIR_Y)], _PHASE_COLORS["aspirate"], "reservoir"
    )
    _scatter_group(
        ax,
        [(sc.RELEASE_BAR_X, sc.RELEASE_BAR_Y)],
        _PHASE_COLORS["eject"],
        "release bar",
    )
    _scatter_group(ax, [(0.0, 0.0)], "black", "HOME")
    _scatter_group(
        ax, [(sc.PARK_FINAL_X, sc.PARK_FINAL_Y)], _PHASE_COLORS["park"], "PARK"
    )

    ax.set_xlabel("X [mm] (Marlin frame)")
    ax.set_ylabel("Y [mm] (Marlin frame — 0=BACK, increasing=FRONT/operator)")
    ax.set_title("Deck layout — top view (row tour)")
    ax.legend(loc="upper left", fontsize=7)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg", facecolor=fig.get_facecolor())
    return out_path


def render_all(profile: MotionProfile, output_dir: Path) -> list[Path]:
    """Render all three motion-profile SVGs into `output_dir`. Returns written paths."""
    sc = _load_showcase()
    spans = _axis_spans(sc)
    return [
        render_kinematics_svg(profile, spans, output_dir / "kinematics_per_axis.svg"),
        render_three_view_path_svg(sc, output_dir / "three_view_path.svg"),
        render_deck_layout_svg(sc, output_dir / "deck_layout_top_view.svg"),
    ]


def main() -> int:
    """Render the active `MOTION_PROFILE` (default MID) to its output dir.

    Returns 0, or 1 if `MOTION_PROFILE` opts out (empty or "off").
    """
    profile = select_profile(os.environ.get("MOTION_PROFILE"))
    if profile is None:
        print(
            "ERROR: MOTION_PROFILE=off (or empty) has no bundled profile to "
            "visualize; unset MOTION_PROFILE or set it to slow|mid|fast.",
            file=sys.stderr,
        )
        return 1
    for out_path in render_all(profile, DEFAULT_OUTPUT_DIR):
        print(f"Rendered: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
