"""i3 Mega print-head carriage → dPette+ 8-channel mount (horizontal-bolt).

Two-piece design:
  - **main**: bolts to the underside of the i3 Mega's horizontal head-
    mount plate via 4× M4 screws in a 21 × 13 mm pattern. Has the back
    half of the upper clamp (D-cavity, flat face toward −Y), a vertical
    post, and the lower horseshoe clamp.
  - **cap**: separate front piece. Mirrors the back-half D-cavity. Bolts
    to the back half via 2× M3 screws running in +Y to capture the
    pipette's Ø27 round upper barrel.

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
tips) < 300 g per `.claude/rules/i3-carriage-payload-budget.md`.

Frame: origin at the centroid of the 4-hole pattern. Z = 0 at the
mount's top face (touches the underside of the horizontal plate).

Usage:
    uv run --extra cad python tools/cad/i3/carriage_dpette_mount.py
"""

import sys
from pathlib import Path

from build123d import Box, Cylinder, Pos, Rot

sys.path.append(str(Path(__file__).resolve().parent.parent))
from barrel_bore import make_clamp_bore
from util.export import export_part

sys.path.pop()


# === Carriage-side measurements (i3 Mega horizontal head-mount plate) ===
SCREW_PITCH_X_MM = 21.0  # 4-hole pattern, X (left ↔ right)
SCREW_PITCH_Y_MM = 13.0  # 4-hole pattern, Y (front ↔ back)
SCREW_HOLE_D_MM = 4.5  # M4 clearance (carriage hole = 4.0)

# === Pipette-side measurements (DLAB dPette+ 8-channel) ===
LOWER_CLAMP_W_MM = 78.0  # fixed-tip manifold cross-section width  (X)
LOWER_CLAMP_D_MM = 11.0  # fixed-tip manifold cross-section depth  (Y)
LOWER_CLAMP_H_MM = 5.0  # manifold vertical extent
UPPER_CLAMP_BORE_D_MM = 27.0  # Ø27 round upper barrel
UPPER_BARREL_HEIGHT_MM = 15.0  # vertical extent of the round section
UPPER_TO_LOWER_SEPARATION_MM = 50.0  # vertical between clamp axes

# === Mount geometry (parametric) ===
TOP_PLATE_W_MM = 35.0  # X width — covers hole pattern + Ø32 upper ring + cap bolts
TOP_PLATE_D_MM = 30.0  # Y depth (back half side; cap adds more in −Y)
TOP_PLATE_T_MM = 8.0  # thickness; doubles as upper-clamp ring height
CLAMP_BORE_CLEARANCE_MM = 0.5
CLAMP_WALL_MM = 2.5  # wall thickness around bores
LOWER_CLAMP_H_PLUS_MM = 1.0  # extra grip beyond manifold height
POST_W_MM = 6.0  # vertical post X (per post; two posts at ±X_OFFSET)
POST_D_MM = 12.0  # vertical post Y
POST_X_OFFSET_MM = (
    18.0  # ±18 mm — outside upper-bore radius (13.75 mm), inside top plate (±17.5 mm)
)
POST_Y_CENTER_MM = 14.0  # behind upper bore (Y > 13.75) and on top of lower clamp's back wall (Y > 5.75)

# === Upper-clamp split (2-piece, M3 bolts in Y direction) ===
UPPER_CAP_D_MM = 8.0  # front cap thickness in Y
UPPER_BOLT_PITCH_X_MM = 28.0  # ±14 mm from bore centre, clear of Ø27 bore
UPPER_BOLT_HOLE_D_MM = 3.4  # M3 clearance
UPPER_BOLT_BACK_LEN_MM = 14.0  # bolt thread engagement into back half

# === Material === (used by mass-budget tests)
PLA_DENSITY_G_PER_CC = 1.24


def _build_top_plate_with_upper_clamp_back():
    """Top plate + back HALF of the split upper clamp.

    The half-cylinder D-cavity opens to −Y; the front cap bolts onto
    this face from −Y to capture the pipette barrel.
    """
    plate = Pos(0, TOP_PLATE_D_MM / 2, -TOP_PLATE_T_MM / 2) * Box(
        TOP_PLATE_W_MM, TOP_PLATE_D_MM, TOP_PLATE_T_MM
    )

    # 4× M4 clearance holes for carriage-mount screws
    for sx in (-1, 1):
        for sy in (-1, 1):
            hole = Pos(
                sx * SCREW_PITCH_X_MM / 2,
                TOP_PLATE_D_MM / 2 + sy * SCREW_PITCH_Y_MM / 2,
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

    # 2× M3 clearance holes through back half (Y axis cylinders),
    # at X = ±14 mm, Z = mid-plate, running from Y=0 to Y=TOP_PLATE_D_MM
    for sx in (-1, 1):
        bolt_hole = (
            Pos(sx * UPPER_BOLT_PITCH_X_MM / 2, TOP_PLATE_D_MM / 2, -TOP_PLATE_T_MM / 2)
            * Rot(90, 0, 0)
            * Cylinder(UPPER_BOLT_HOLE_D_MM / 2, TOP_PLATE_D_MM + 2)
        )
        plate = plate - bolt_hole

    return plate


def _build_lower_clamp(z_center: float):
    """Open-horseshoe clamp around the fixed-tip manifold (78 × 11 × 5 mm)."""
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
    return ring - slot


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
    """Build the front cap of the upper clamp.

    Mirrors the back half's D-cavity. Bolts to the back half from −Y
    via 2× M3 screws to capture the pipette's Ø27 round upper barrel.
    """
    # Mass: ~3 g PLA (volume ~2.5 cc * 1.24 g/cc).

    # Cap occupies Y from −UPPER_CAP_D_MM to 0 (sits in front of back half).
    cap = Pos(0, -UPPER_CAP_D_MM / 2, -TOP_PLATE_T_MM / 2) * Box(
        TOP_PLATE_W_MM, UPPER_CAP_D_MM, TOP_PLATE_T_MM
    )

    # D-cavity: half-bore facing +Y (toward back half). Centre at Y=0;
    # the host cap's Y extent clips the cylinder into a D shape.
    bore_full = Pos(0, 0, -TOP_PLATE_T_MM / 2) * make_clamp_bore(
        UPPER_CLAMP_BORE_D_MM, TOP_PLATE_T_MM + 2, CLAMP_BORE_CLEARANCE_MM
    )
    cap = cap - bore_full

    # 2× M3 clearance holes through cap (Y axis cylinders)
    for sx in (-1, 1):
        bolt_hole = (
            Pos(
                sx * UPPER_BOLT_PITCH_X_MM / 2, -UPPER_CAP_D_MM / 2, -TOP_PLATE_T_MM / 2
            )
            * Rot(90, 0, 0)
            * Cylinder(UPPER_BOLT_HOLE_D_MM / 2, UPPER_CAP_D_MM + 2)
        )
        cap = cap - bolt_hole

    return cap


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
