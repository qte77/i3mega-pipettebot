"""i3 Mega print-head carriage → dPette+ 8-channel mount.

Two schemes share the same main + cap geometry:
  - **scheme a** (`build_carriage_dpette_mount_main`): horizontal-bolt
    only. 4× M4 in 21 × 13 mm pattern on the carriage's horizontal
    head-mount plate. Lighter, simpler.
  - **scheme b** (`build_carriage_dpette_mount_main_lbracket`): scheme a
    + an L-bracket reinforcement that adds 2× M4 bolts engaging the top
    of the carriage's vertical plate (28 mm pitch, 27.5 mm above the
    horizontal plate). Resists pitch torque under XY acceleration.

Two-piece main + cap (shared by both schemes):
  - **main**: bolts to the underside of the i3 Mega's horizontal head-
    mount plate via 4× M4 screws in a 21 × 13 mm pattern. Has the back
    half of the upper clamp (D-cavity, flat face toward −Y), a vertical
    post, and the lower horseshoe clamp.
  - **cap**: separate front horseshoe piece. Mirrors the back-half
    D-cavity. CA-glues / friction-fits to the back half front face to
    capture the pipette's Ø24.5 upper barrel. Flush with the top plate
    in Z; 30 mm wide in X (narrower than the 35 mm plate); 23.34 mm
    deep in Y (sides extend ~10.8 mm past the bore center per dry-fit).

The upper clamp must be two-piece because the dPette+ is one rigid
unit (lower body, upper barrel, top section all permanently joined),
so lateral horseshoe insertion of the upper barrel is blocked by the
wider sections above and below.

Lower clamp stays a single-piece horseshoe (open to −Y) — only the
fixed-tip manifold needs to fit; nothing wider passes through it.

Pipette anatomy (per measurements):
  - Fixed-tip manifold: 78 × 11 × 5 mm, at z=0 above tip-cone tips
  - Ø27 round upper barrel: 15 mm tall, centred ~50 mm above cones
  - Wider sections above (display, rotatable top) and below (volume
    body) prevent axial insertion through any Ø27 horseshoe

Mass budget: total carriage payload (main + cap + 250 g pipette + 3 g
tips) < 300 g per `.claude/rules/i3-carriage-payload-budget.md`. Scheme
b is heavier than scheme a but stays within budget.

Frame: origin at the centroid of the 4-hole pattern. Z = 0 at the
mount's top face (touches the underside of the horizontal plate).
+Y is toward the back of the carriage (away from the pipette).

Usage:
    uv run --extra cad python tools/cad/i3/carriage_dpette_mount.py
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
    UPPER_CLAMP_BORE_D_MM,
    UPPER_TO_LOWER_SEPARATION_MM,
    VPLATE_TOP_HOLE_D_MM,
    VPLATE_TOP_HOLE_PITCH_MM,
    VPLATE_TOP_OFFSET_MM,
    VPLATE_TOP_X_OFFSET_MM,
)

# Re-exports — accessed reflectively as `mount.X` by mass-budget / geometry tests.
# The `as X` self-rename is the PEP 484 idiom for an explicit re-export.
from measurements import PLA_DENSITY_G_PER_CC as PLA_DENSITY_G_PER_CC
from measurements import UPPER_BARREL_HEIGHT_MM as UPPER_BARREL_HEIGHT_MM
from util.export import export_part

sys.path.pop()


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
CLAMP_BORE_CLEARANCE_MM = 0.5  # diametral; tight clamp on Ø27 barrel
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
# 3.67 mm → 21.34 mm. v4 added another 2 mm → 23.34 mm.
UPPER_CAP_D_MM = 23.34
# Cap bore is a capsule/slot (not a circle) to give the barrel axial
# play in Y. Short axis = UPPER_CLAMP_BORE_D_MM (matches the main
# piece's circular bore at the Y=0 mating face); long axis grows with
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

    The half-cylinder D-cavity opens to −Y; the front cap bolts onto
    this face from −Y to capture the pipette barrel.
    """
    plate = Pos(0, TOP_PLATE_D_MM / 2, -TOP_PLATE_T_MM / 2) * Box(
        TOP_PLATE_W_MM, TOP_PLATE_D_MM, TOP_PLATE_T_MM
    )

    # 4× M4 clearance holes for carriage-mount screws.
    # Anchored such that the mount's front edge sits FRONT_OVERHANG_MM in front
    # of the carriage's front edge; HOLE_FROM_FRONT_MM is the carriage's
    # front-edge → first-hole distance, so on the mount the first hole sits at
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
        UPPER_CLAMP_BORE_D_MM, TOP_PLATE_T_MM + 2, CLAMP_BORE_CLEARANCE_MM
    )
    plate = plate - bore_full

    # Upper clamp cap (horseshoe) glues to the back face — no bolt holes.

    return plate


def _build_lower_clamp(z_center: float):
    """Horseshoe clamp + J-hooks around the fixed-tip manifold (78 × 11 × 5 mm).

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

    # Slot opening to −Y: removes the front wall, exposing the bore
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
    """Two vertical posts BEHIND the upper bore, one on each side of the pipette.

    Centred at Y = POST_Y_CENTER_MM (≈ 14 mm) so each post lands on real
    plate material above (top plate's back-of-D zone, Y > 13.75) and on
    real lower-clamp material below (back wall, Y ∈ [5.75, 11]). A
    single central post at Y=0 would intersect both bores and "float"
    in the slicer (no material connection).
    """
    h = z_top - z_bottom
    z_center = (z_top + z_bottom) / 2
    posts = None
    for sx in (-1, 1):
        post = Pos(sx * POST_X_OFFSET_MM, POST_Y_CENTER_MM, z_center) * Box(
            POST_W_MM, POST_D_MM, h
        )
        posts = post if posts is None else posts + post
    return posts


def build_carriage_dpette_mount_main():
    """Build the main mount piece (top plate + back half + post + lower clamp).

    Top face at Z = 0 (touches underside of horizontal head-mount plate).
    """
    # Mass: ~16 g PLA (volume ~13 cc * 1.24 g/cc).
    # With cap (~3 g) + 250 g dPette+ + 3 g tips = ~272 g, under 300 g cap.

    top_plate = _build_top_plate_with_upper_clamp_back()

    upper_axis_z = -TOP_PLATE_T_MM / 2
    lower_axis_z = upper_axis_z - UPPER_TO_LOWER_SEPARATION_MM
    lower_clamp_h = LOWER_CLAMP_H_MM + LOWER_CLAMP_H_PLUS_MM
    lower_top = lower_axis_z + lower_clamp_h / 2

    posts = _build_posts(z_top=-TOP_PLATE_T_MM, z_bottom=lower_top)
    lower_clamp = _build_lower_clamp(lower_axis_z)

    return top_plate + posts + lower_clamp


def build_carriage_dpette_mount_cap():
    """Build the front cap (horseshoe) of the upper clamp.

    Mirrors the back half's D-cavity. Attaches to the back half via CA
    glue or friction fit (no bolts). Sits flush with the top plate in Z
    and is narrower in X (~30 mm vs the 35 mm plate). Symmetric about
    the Y axis; much shorter in Y than the main piece.

    Bore is a Y-elongated capsule (slot), not a full circle: short axis
    matches the main piece's circular bore at the Y=0 mating face; long
    axis gives the barrel axial play in Y.
    """
    # Mass: ~2 g PLA (volume ~1.6 cc * 1.24 g/cc).

    # Cap occupies Y from −UPPER_CAP_D_MM to 0, X = ±UPPER_CAP_W_MM/2.
    cap = Pos(0, -UPPER_CAP_D_MM / 2, -TOP_PLATE_T_MM / 2) * Box(
        UPPER_CAP_W_MM, UPPER_CAP_D_MM, TOP_PLATE_T_MM
    )

    # Capsule-slot bore: centered at origin, long axis along Y. The two
    # semicircles at the Y ends (radius = UPPER_CLAMP_BORE_D_MM/2 +
    # clearance/2) connect via a rectangle of length
    # UPPER_CAP_BORE_LONG_MM − short-axis-with-clearance.
    bore_d_eff = UPPER_CLAMP_BORE_D_MM + CLAMP_BORE_CLEARANCE_MM
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
    """L-bracket reinforcement: vertical web + horizontal flange + 2× M4 holes.

    Web rises from the back edge of the top plate (Y = TOP_PLATE_D_MM)
    up to the V-plate top hole height. Flange caps the web at z =
    VPLATE_TOP_OFFSET_MM and overhangs +Y over the V-plate top so the
    two M4 bolts thread DOWN (-Z) into the V-plate's top threaded holes.
    """
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


def build_carriage_dpette_mount_main_lbracket():
    """Build scheme b: main piece + L-bracket reinforcement to V-plate top.

    Adds a vertical web at the back edge of the top plate climbing to z =
    VPLATE_TOP_OFFSET_MM, capped by a flange with 2× M4 clearance holes
    that engage the V-plate's top threaded holes. Cap piece is shared
    with scheme a (`build_carriage_dpette_mount_cap`).
    """
    # Mass: ~23 g PLA (~16 g main + ~7 g L-bracket; total volume ~18 cc * 1.24 g/cc).
    # With cap (~3 g) + 250 g dPette+ + 3 g tips = ~279 g, under 300 g cap.
    return build_carriage_dpette_mount_main() + _build_lbracket_reinforcement()


def build_carriage_dpette_mount():
    """Backwards-compat alias — returns the main piece only.

    parts.json now ships two separate entries (main + cap); this
    function exists so any caller still using the old single-piece
    name gets the main piece.
    """
    return build_carriage_dpette_mount_main()


if __name__ == "__main__":
    export_part(build_carriage_dpette_mount_main(), "i3", "carriage_dpette_mount_main")
    export_part(build_carriage_dpette_mount_cap(), "i3", "carriage_dpette_mount_cap")
    export_part(
        build_carriage_dpette_mount_main_lbracket(),
        "i3",
        "carriage_dpette_mount_main_lbracket",
    )
