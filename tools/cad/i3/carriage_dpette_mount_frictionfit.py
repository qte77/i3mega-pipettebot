"""i3 Mega print-head carriage → dPette+ 8-channel mount — friction-fit testing variant.

**Testing variant, not the production target.** `carriage_dpette_mount.py`
(same directory) ships the production M3-bolted upper-clamp design. This
module is a separate, self-contained iteration that replaces the bolted cap
with a glue/friction-fit cap, reached through four rounds of physical
dry-fit testing (see the `UPPER_CAP_D_MM` comment below for the v1-v4
progression). It also carries its own re-measured pipette bore/separation
values that the dry-fit testing was actually done against.

This module intentionally does NOT share `UPPER_CLAMP_BORE_D_MM` /
`UPPER_TO_LOWER_SEPARATION_MM` with `measurements.py` — those shared
constants (Ø27 mm, 50 mm) are what the production bolted design is built
and validated against. This module's local
`FRICTIONFIT_UPPER_CLAMP_BORE_D_MM` (24.5 mm) and
`FRICTIONFIT_UPPER_TO_LOWER_SEPARATION_MM` (80.5 mm) are re-measured values
from this iteration's own dry-fit sessions. Promoting either to the shared
production measurements is a separate decision requiring physical
validation on the production bolted design; not done here.

**Why this variant exists at all**: issue #75 documents that this exact
friction-fit design was abandoned mid-iteration for two reasons — the bore
size never converged after five rounds ("v5 is still the wrong size"), and
glue/friction fit isn't mechanically robust (fails under vibration,
irreversible, not serviceable). #75 asks to reintroduce M3 bolts, which is
exactly what `carriage_dpette_mount.py`'s production design already does
(matching `UPPER_BOLT_PITCH_X_MM` / `UPPER_BOLT_HOLE_D_MM` constants). #75
is only half-resolved though: its bore re-measurement request was not
carried over — the production bolted design still uses the original Ø27 mm
bore, not the Ø24.5 mm this module's dry-fit sessions converged on. Kept
here as testing/reference, not because it's a live candidate to replace
the bolted design.

Two-piece main + cap:
  - **main**: bolts to the underside of the i3 Mega's horizontal head-
    mount plate via 4x M4 screws in a 21 x 13 mm pattern. Has the back
    half of the upper clamp (D-cavity, flat face toward -Y), a vertical
    post, and a horseshoe lower clamp with J-hooks (see `_build_lower_clamp`)
    that grip the fixed-tip manifold and resist yaw rotation.
  - **cap**: separate front horseshoe piece. Mirrors the back-half
    D-cavity. CA-glues / friction-fits to the back half front face to
    capture the pipette's Ø24.5 upper barrel. Flush with the top plate
    in Z; 30 mm wide in X (narrower than the 35 mm plate); 23.34 mm deep
    in Y (sides extend ~10.8 mm past the bore center per dry-fit).

The upper clamp must be two-piece because the dPette+ is one rigid unit
(lower body, upper barrel, top section all permanently joined), so lateral
horseshoe insertion of the upper barrel is blocked by the wider sections
above and below.

Usage:
    uv run --extra cad python tools/cad/i3/carriage_dpette_mount_frictionfit.py
"""

import sys
from pathlib import Path

from build123d import Box, Cylinder, Pos

sys.path.append(str(Path(__file__).resolve().parent.parent))
from barrel_bore import make_clamp_bore
from measurements import (
    HOLE_FROM_FRONT_MM,
    LOWER_CLAMP_D_MM,
    LOWER_CLAMP_H_MM,
    LOWER_CLAMP_W_MM,
    SCREW_HOLE_D_MM,
    SCREW_PITCH_X_MM,
    SCREW_PITCH_Y_MM,
    VPLATE_TOP_HOLE_D_MM,
    VPLATE_TOP_HOLE_PITCH_MM,
    VPLATE_TOP_OFFSET_MM,
    VPLATE_TOP_X_OFFSET_MM,
)

# Re-export for reflective access as `mount.X` by mass-budget tests.
from measurements import PLA_DENSITY_G_PER_CC as PLA_DENSITY_G_PER_CC
from util.export import export_part

sys.path.pop()

__all__ = [
    "PLA_DENSITY_G_PER_CC",
    "build_carriage_dpette_mount_cap_frictionfit",
    "build_carriage_dpette_mount_main_frictionfit",
    "build_carriage_dpette_mount_main_lbracket_frictionfit",
]

# === Re-measured pipette dimensions (this iteration's own dry-fit sessions) ===
# Local to this module — see module docstring for why these aren't promoted
# to the shared tools/cad/measurements.py constants.
FRICTIONFIT_UPPER_CLAMP_BORE_D_MM = 24.5  # re-measured + clearance, per cap dry-fit
FRICTIONFIT_UPPER_TO_LOWER_SEPARATION_MM = 80.5  # re-measured axis-to-axis

# === Mount geometry (parametric — design knobs for this specific mount) ===
TOP_PLATE_W_MM = 35.0  # X width — covers hole pattern + Ø32 upper ring + cap bolts
# Mount extends FRONT_OVERHANG_MM past the carriage's front edge so there's more
# material between the upper-clamp bore (at Y = 0) and the M4 mounting holes.
# Back edge of the mount aligns with the carriage's back edge.
FRONT_OVERHANG_MM = 15.0
# TOP_PLATE_D_MM = FRONT_OVERHANG + HOLE_FROM_FRONT + SCREW_PITCH_Y + HOLE_FROM_BACK
#                = 15 + 45 + 13 + 12 = 85
TOP_PLATE_D_MM = 85.0
TOP_PLATE_T_MM = 5.0  # thickness; doubles as upper-clamp ring height
CLAMP_BORE_CLEARANCE_MM = 0.5  # diametral; tight clamp on Ø24.5 barrel
CLAMP_WALL_MM = 2.5  # wall thickness around bores
LOWER_CLAMP_H_PLUS_MM = 1.0  # extra grip beyond manifold height
# J-hooks at lower-clamp side walls: prevent yaw rotation of the pipette body.
# Each side wall extends LOWER_CLAMP_HOOK_OUT_MM in -Y, then turns
# LOWER_CLAMP_HOOK_IN_MM toward the centerline. Manifold must be inserted
# from above (+Z) because the front gap shrinks below 78 mm.
LOWER_CLAMP_HOOK_OUT_MM = 20.0  # forward arm length (Y)
LOWER_CLAMP_HOOK_IN_MM = (
    17.5  # inward hook span toward centerline (X); tip face = 20 mm total
)
POST_W_MM = 5.0  # vertical post X (per post; two posts at ±X_OFFSET)
POST_D_MM = 12.0  # vertical post Y
POST_X_OFFSET_MM = (
    18.0  # ±18 mm — outside upper-bore radius (13.75 mm), inside top plate (±17.5 mm)
)
POST_Y_CENTER_MM = 14.0  # behind upper bore (Y > 13.75) and on top of lower clamp's back wall (Y > 5.75)

# === Upper-clamp split (2-piece, glue/friction fit, no bolts) ===
# Cap depth in Y: bore radius ~12.5 mm (Ø24.5 + clearance) + front wall.
# v1 (14 mm) and v2 (17.67 mm) were too shallow per dry-fit; v3 added
# 3.67 mm -> 21.34 mm. v4 added another 2 mm -> 23.34 mm.
UPPER_CAP_D_MM = 23.34
# Cap bore is a capsule/slot (not a circle) to give the barrel axial
# play in Y. Short axis = FRICTIONFIT_UPPER_CLAMP_BORE_D_MM (matches the
# main piece's circular bore at the Y=0 mating face); long axis grows with
# the cap (v3: 28 mm; v4: 30 mm) to keep ~7.3 mm of front wall.
# Main piece stays circular — only the cap is slotted.
UPPER_CAP_BORE_LONG_MM = 30.0
# Cap width in X: narrower than the 35 mm top plate per user spec
# (~30 mm = bore Ø24 + 3 mm wall each side).
UPPER_CAP_W_MM = 30.0

# === L-bracket reinforcement (scheme b) — mount-side design knobs ===
# V-plate hole pattern is imported from measurements.py (VPLATE_TOP_*).
LBRACKET_WEB_T_MM = 4.0  # vertical web Y-thickness
LBRACKET_FLANGE_W_MM = (
    38.0  # flange X-width (28 mm pitch + ~5 mm bolt-head clearance per side)
)
LBRACKET_FLANGE_D_MM = 12.0  # flange Y-depth: spans web + V-plate top overhang
LBRACKET_FLANGE_T_MM = 4.0  # flange Z-thickness


def _build_top_plate_with_upper_clamp_back():
    """Top plate + back HALF of the split upper clamp.

    The half-cylinder D-cavity opens to -Y; the front cap glues/friction-fits
    onto this face from -Y to capture the pipette barrel. No bolt holes —
    unlike the production bolted design, this cap has nothing to bolt to.
    """
    plate = Pos(0, TOP_PLATE_D_MM / 2, -TOP_PLATE_T_MM / 2) * Box(
        TOP_PLATE_W_MM, TOP_PLATE_D_MM, TOP_PLATE_T_MM
    )

    # 4x M4 clearance holes for carriage-mount screws.
    # Anchored such that the mount's front edge sits FRONT_OVERHANG_MM in front
    # of the carriage's front edge; HOLE_FROM_FRONT_MM is the carriage's
    # front-edge -> first-hole distance, so on the mount the first hole sits at
    # Y = FRONT_OVERHANG_MM + HOLE_FROM_FRONT_MM.
    hole_y_center = FRONT_OVERHANG_MM + HOLE_FROM_FRONT_MM + SCREW_PITCH_Y_MM / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            hole = Pos(
                sx * SCREW_PITCH_X_MM / 2,
                hole_y_center + sy * SCREW_PITCH_Y_MM / 2,
                -TOP_PLATE_T_MM / 2,
            ) * Cylinder(SCREW_HOLE_D_MM / 2, TOP_PLATE_T_MM + 2)
            plate = plate - hole

    # D-cavity: subtract the half-cylinder bore at Y < TOP_PLATE_D_MM/2.
    # The pipette axis is at Y = 0 (front face of back half); the host
    # plate's Y extent clips the cylinder into a D shape.
    bore_full = Pos(0, 0, -TOP_PLATE_T_MM / 2) * make_clamp_bore(
        FRICTIONFIT_UPPER_CLAMP_BORE_D_MM, TOP_PLATE_T_MM + 2, CLAMP_BORE_CLEARANCE_MM
    )
    plate = plate - bore_full

    return plate


def _build_lower_clamp(z_center: float):
    """Horseshoe clamp + J-hooks around the fixed-tip manifold (78 x 11 x 5 mm).

    Back wall + two side walls form the horseshoe (open to -Y). Each side
    wall then extends LOWER_CLAMP_HOOK_OUT_MM forward and turns
    LOWER_CLAMP_HOOK_IN_MM inward — the resulting J prevents yaw rotation
    of the pipette. Manifold inserts from above.
    """
    bore_w = LOWER_CLAMP_W_MM + CLAMP_BORE_CLEARANCE_MM
    bore_d = LOWER_CLAMP_D_MM + CLAMP_BORE_CLEARANCE_MM
    outer_w = bore_w + 2 * CLAMP_WALL_MM
    outer_d = bore_d + 2 * CLAMP_WALL_MM
    h = LOWER_CLAMP_H_MM + LOWER_CLAMP_H_PLUS_MM

    outer = Pos(0, 0, z_center) * Box(outer_w, outer_d, h)
    bore = Pos(0, 0, z_center) * Box(bore_w, bore_d, h + 2)
    ring = outer - bore

    # Slot opening to -Y: removes the front wall, exposing the bore
    slot_d = outer_d / 2 + 1
    slot = Pos(0, -slot_d / 2, z_center) * Box(bore_w, slot_d, h + 2)
    ring = ring - slot

    # J-hooks: forward arm + inward tip at each side, OR'd onto the horseshoe.
    arm_x_center = (bore_w + outer_w) / 4  # = mid of side wall in |X|
    arm_y_center = -outer_d / 2 - LOWER_CLAMP_HOOK_OUT_MM / 2
    # Tip overlaps with arm at the corner (spans inward from outer wall edge)
    tip_x_width = LOWER_CLAMP_HOOK_IN_MM + CLAMP_WALL_MM
    tip_x_center = outer_w / 2 - tip_x_width / 2
    tip_y_center = -outer_d / 2 - LOWER_CLAMP_HOOK_OUT_MM + CLAMP_WALL_MM / 2
    for sx in (-1, 1):
        arm = Pos(sx * arm_x_center, arm_y_center, z_center) * Box(
            CLAMP_WALL_MM, LOWER_CLAMP_HOOK_OUT_MM, h
        )
        tip = Pos(sx * tip_x_center, tip_y_center, z_center) * Box(
            tip_x_width, CLAMP_WALL_MM, h
        )
        ring = ring + arm + tip

    return ring


def _build_posts(z_top: float, z_bottom: float):
    """Two vertical posts BEHIND the upper bore, one on each side of the pipette."""
    h = z_top - z_bottom
    z_center = (z_top + z_bottom) / 2
    posts = None
    for sx in (-1, 1):
        post = Pos(sx * POST_X_OFFSET_MM, POST_Y_CENTER_MM, z_center) * Box(
            POST_W_MM, POST_D_MM, h
        )
        posts = post if posts is None else posts + post
    return posts


def build_carriage_dpette_mount_main_frictionfit():
    """Build the main mount piece (top plate + back half + posts + lower clamp).

    Top face at Z = 0 (touches underside of horizontal head-mount plate).
    """
    # Mass: ~31.2 g PLA (measured via shape.volume * PLA_DENSITY_G_PER_CC).
    # With cap (~2.4 g) + 250 g dPette+ + 3 g tips = ~286.6 g, 13.4 g under
    # the 300 g cap.

    top_plate = _build_top_plate_with_upper_clamp_back()

    upper_axis_z = -TOP_PLATE_T_MM / 2
    lower_axis_z = upper_axis_z - FRICTIONFIT_UPPER_TO_LOWER_SEPARATION_MM
    lower_clamp_h = LOWER_CLAMP_H_MM + LOWER_CLAMP_H_PLUS_MM
    lower_top = lower_axis_z + lower_clamp_h / 2

    posts = _build_posts(z_top=-TOP_PLATE_T_MM, z_bottom=lower_top)
    lower_clamp = _build_lower_clamp(lower_axis_z)

    return top_plate + posts + lower_clamp


def build_carriage_dpette_mount_cap_frictionfit():
    """Build the front cap (horseshoe) of the upper clamp.

    Mirrors the back half's D-cavity. Attaches via CA glue or friction fit
    (no bolts). Bore is a Y-elongated capsule (slot), not a full circle:
    short axis matches the main piece's circular bore at the Y=0 mating
    face; long axis gives the barrel axial play in Y.
    """
    # Mass: ~2.4 g PLA (measured via shape.volume * PLA_DENSITY_G_PER_CC).

    # Cap occupies Y from -UPPER_CAP_D_MM to 0, X = ±UPPER_CAP_W_MM/2.
    cap = Pos(0, -UPPER_CAP_D_MM / 2, -TOP_PLATE_T_MM / 2) * Box(
        UPPER_CAP_W_MM, UPPER_CAP_D_MM, TOP_PLATE_T_MM
    )

    bore_d_eff = FRICTIONFIT_UPPER_CLAMP_BORE_D_MM + CLAMP_BORE_CLEARANCE_MM
    r_bore = bore_d_eff / 2
    rect_len_y = UPPER_CAP_BORE_LONG_MM - bore_d_eff
    slot_rect = Pos(0, 0, -TOP_PLATE_T_MM / 2) * Box(
        bore_d_eff, rect_len_y, TOP_PLATE_T_MM + 2
    )
    slot_top = Pos(0, rect_len_y / 2, -TOP_PLATE_T_MM / 2) * Cylinder(
        r_bore, TOP_PLATE_T_MM + 2
    )
    slot_bot = Pos(0, -rect_len_y / 2, -TOP_PLATE_T_MM / 2) * Cylinder(
        r_bore, TOP_PLATE_T_MM + 2
    )
    cap = cap - slot_rect - slot_top - slot_bot

    return cap


def _build_lbracket_reinforcement():
    """L-bracket reinforcement: vertical web + horizontal flange + 2x M4 holes."""
    web_y_center = TOP_PLATE_D_MM - LBRACKET_WEB_T_MM / 2
    web = Pos(0, web_y_center, VPLATE_TOP_OFFSET_MM / 2) * Box(
        TOP_PLATE_W_MM, LBRACKET_WEB_T_MM, VPLATE_TOP_OFFSET_MM
    )

    flange_y_min = TOP_PLATE_D_MM - LBRACKET_WEB_T_MM
    flange_y_center = flange_y_min + LBRACKET_FLANGE_D_MM / 2
    flange_z_center = VPLATE_TOP_OFFSET_MM + LBRACKET_FLANGE_T_MM / 2
    flange = Pos(VPLATE_TOP_X_OFFSET_MM, flange_y_center, flange_z_center) * Box(
        LBRACKET_FLANGE_W_MM, LBRACKET_FLANGE_D_MM, LBRACKET_FLANGE_T_MM
    )

    bolt_y = TOP_PLATE_D_MM  # at the V-plate front face
    bracket = web + flange
    for sx in (-1, 1):
        hole = Pos(
            VPLATE_TOP_X_OFFSET_MM + sx * VPLATE_TOP_HOLE_PITCH_MM / 2,
            bolt_y,
            flange_z_center,
        ) * Cylinder(VPLATE_TOP_HOLE_D_MM / 2, LBRACKET_FLANGE_T_MM + 2)
        bracket = bracket - hole

    return bracket


def build_carriage_dpette_mount_main_lbracket_frictionfit():
    """Build scheme b: main piece + L-bracket reinforcement to V-plate top."""
    # Mass: ~38.1 g PLA total (main + L-bracket combined, measured via
    # shape.volume * PLA_DENSITY_G_PER_CC).
    # With cap (~2.4 g) + 250 g dPette+ + 3 g tips = ~293.5 g, 6.5 g under
    # the 300 g cap — tighter than the bolted scheme b (see
    # carriage_dpette_mount.py), flagged in the PR for visibility.
    return (
        build_carriage_dpette_mount_main_frictionfit() + _build_lbracket_reinforcement()
    )


if __name__ == "__main__":
    export_part(
        build_carriage_dpette_mount_main_frictionfit(),
        "i3",
        "carriage_dpette_mount_main_frictionfit",
    )
    export_part(
        build_carriage_dpette_mount_cap_frictionfit(),
        "i3",
        "carriage_dpette_mount_cap_frictionfit",
    )
    export_part(
        build_carriage_dpette_mount_main_lbracket_frictionfit(),
        "i3",
        "carriage_dpette_mount_main_lbracket_frictionfit",
    )
