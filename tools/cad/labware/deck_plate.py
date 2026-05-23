"""Deck plate for the i3 Mega bed (219.8 x 219.8 mm).

Holds four labware items in XY position via shallow lip fences. Split
at X=100 mm into two halves so each piece fits a 250 x 210 mm Prusa
MK4 print bed and can be re-printed independently.

Each half:
  - 2 mm flat base (i3 bed-clip max grip thickness)
  - 2 mm tall lip fences around each labware footprint (0.5 mm slip fit)
  - No interlock between halves; both clipped to the i3 bed at edges
  - Deck shrunk 0.2 mm from the 220 bed envelope so the bed clips can
    reach inward across the deck-plate top surface — no clamp cutouts
    needed in the plate itself

Slot positions match docs/deck-plate.drawio (v1 layout, user-annotated).
The rows-example (`examples/showcase_v0_full_pipettebot_rows.py`) anchor
constants do NOT match this layout; they need a follow-up update (tip
box moved BACK, well plate FRONT-overhanging, reservoir to FRONT).

Coordinate convention: build123d (X, Y) maps directly to Marlin (X, Y).
Marlin frame has Y=0 at the bed BACK, Y=220 at the bed FRONT.

Usage:
    uv run --extra cad python tools/cad/labware/deck_plate.py
"""

import sys
from pathlib import Path

from build123d import Box, Plane, Pos, mirror

sys.path.append(str(Path(__file__).resolve().parent.parent))
from util.export import export_part

sys.path.pop()

# --- Plate / fence parameters (all in mm) ---
DECK_WIDTH = 219.8  # X span — 0.1 mm shrink from 220 per side for clip clearance
DECK_DEPTH = 229.8  # Y span — extended 10 mm beyond the bed's 219.8
# so each half prints to ~Y=219 after the MK4's
# ~209 mm Y truncation
BASE_T = 4.0  # base thickness — rigid main body
CLAMP_ZONE_T = 2.0  # base thickness at clamp pockets — i3 bed-clip max grip
LIP_H = 2.0  # lip fence height (sits on top of the base)
LIP_T = 1.5  # lip wall thickness
CLEARANCE = 0.5  # labware-to-lip slip fit
SPLIT_X = 100.0  # X split line (left / right halves)

# --- Clamp pockets (8 perimeter notches where bed clips engage) ---
# Each pocket: 20 mm along the edge x 10 mm into the deck. Cuts away
# the top (BASE_T - CLAMP_ZONE_T) = 3 mm so the clip grips a 2 mm
# tall top face at Z = CLAMP_ZONE_T.
CLAMP_W = 20.0  # along edge direction
CLAMP_D = 10.0  # into the deck (perpendicular to edge)
# (centre_x_mm, centre_y_mm, edge): edge in {top, bottom, left, right}
# Positions chosen to avoid the labware through-holes — pockets at
# the perimeter that overlap a labware cutout get eaten by the
# subtract and become invisible.
CLAMP_POSITIONS = (
    (30.0, 0.0, "top"),  # c1 — clear (above bin Y top=15)
    (190.0, 0.0, "top"),  # c2 — clear (above tip box Y top=25)
    (DECK_WIDTH, 10.0, "right"),  # c3 — above tip box (was Y=80, inside tip box)
    (DECK_WIDTH, 225.0, "right"),  # c4 — below reservoir (was Y=160, inside reservoir)
    (
        190.0,
        DECK_DEPTH,
        "bottom",
    ),  # c5 — clear (reservoir front=210 < deck bottom=229.8)
    (
        120.0,
        DECK_DEPTH,
        "bottom",
    ),  # c6 — between well plate X and reservoir Y (was X=80, inside well plate)
    (0.0, 170.0, "left"),  # c7 — between bin and well plate left edges (X<10 = clear)
    (
        0.0,
        110.0,
        "left",
    ),  # c8 — between bin (Y bottom=102) and well plate (Y top=104.5) (was Y=80, inside bin)
)

# --- Labware footprints (Marlin frame, mm) ---
# Source: docs/deck-plate.drawio (v1, user-annotated layout).

# Used-tips bin: empty SBS-footprint container. Catches tips released
# by the dPette at the release bar (X=0, Y=220). The bin is not 3D-
# printed — this is just a lip-fence slot for whatever container the
# user places. OVERHANGS LEFT (X < 0) by 55 mm so the 5.5 cm gap to
# the tip box (X=127) holds. Left lip auto-cropped at X=0.
# 1.5 cm back margin (Y top = 15).
BIN_X = 8.5
BIN_Y = 58.5  # centre Y; span = 15..102
BIN_LONG = 87.0  # along Y
BIN_SHORT = 127.0  # along X

# Tip box: 83 x 122 mm (user-supplied; smaller than SBS standard).
# Back-right, no overhang. 2.5 cm back margin (Y top=25), 1 cm right
# margin (right edge X=210). Bin right at X=72; 5.5 cm gap to tip
# box left at X=127. Centre X=168.5.
TIP_BOX_X = 168.5
TIP_BOX_Y = 86.0
TIP_BOX_LONG = 122.0  # along Y
TIP_BOX_SHORT = 83.0  # along X

# 96-well plate: SBS standard 85.5 x 127.8 mm. Front-left, no overlap
# with bin: 0.25 cm gap below bin bottom (bin Y=15..102; well-plate
# Y top = 104.5). Front edge at Y=232.3 — OVERHANGS Y > 219.8 by
# 12.5 mm. Front lip auto-cropped at the deck envelope (U-shape open
# toward front).
WELL_X = 52.75
WELL_Y = 168.4  # centre Y; span = 104.5..232.3
WELL_LONG = 127.8  # along Y
WELL_SHORT = 85.5  # along X

# Reservoir: 140 x 45 mm trough at the front. Touches right deck edge
# (right edge at X=220, deck right at X=219.8 — 0.2 mm overhang auto-
# cropped by the envelope intersection). Slight overlap with the 96-
# well plate at X=80..95.5, Y=165..192 — acceptable (parts swap).
RESERVOIR_X = 150.0
RESERVOIR_Y = 186.0  # was 187.5; back edge -3 mm to Y=162
RESERVOIR_LONG = 48.0  # along Y (was 45; +3 mm at the back)
RESERVOIR_SHORT = 140.0  # along X

_SLOTS = (
    (BIN_X, BIN_Y, BIN_LONG, BIN_SHORT),
    (TIP_BOX_X, TIP_BOX_Y, TIP_BOX_LONG, TIP_BOX_SHORT),
    (WELL_X, WELL_Y, WELL_LONG, WELL_SHORT),
    (RESERVOIR_X, RESERVOIR_Y, RESERVOIR_LONG, RESERVOIR_SHORT),
)


def _slot_lip(cx_mm, cy_mm, long_y_mm, short_x_mm):
    """Hollow rectangular lip fence at (cx, cy) in the Marlin frame.

    `long_y_mm` is the footprint dimension along Y; `short_x_mm` along X.
    """
    inner_y = long_y_mm + CLEARANCE * 2
    inner_x = short_x_mm + CLEARANCE * 2
    outer_y = inner_y + LIP_T * 2
    outer_x = inner_x + LIP_T * 2
    z_center = BASE_T + LIP_H / 2
    outer = Pos(cx_mm, cy_mm, z_center) * Box(outer_x, outer_y, LIP_H)
    inner = Pos(cx_mm, cy_mm, z_center) * Box(inner_x, inner_y, LIP_H + 1)
    return outer - inner


def _slot_hole(cx_mm, cy_mm, long_y_mm, short_x_mm):
    """Through-hole matching the labware footprint. The labware drops
    completely through the deck and rests on the i3 bed; the lip ring
    constrains XY. Z is oversized so the Boolean cut is clean."""
    return Pos(cx_mm, cy_mm, BASE_T / 2) * Box(short_x_mm, long_y_mm, BASE_T * 2)


def _clamp_pocket(cx_mm, cy_mm, edge):
    """Step-down at a perimeter clamp zone. Cuts away the top
    (BASE_T - CLAMP_ZONE_T) mm over a CLAMP_W (along edge) x CLAMP_D
    (into deck) footprint, so the bed clip can grip a CLAMP_ZONE_T mm
    top face at this position."""
    cut_h = BASE_T - CLAMP_ZONE_T
    z_center = CLAMP_ZONE_T + cut_h / 2
    if edge in ("top", "bottom"):
        w_x, w_y = CLAMP_W, CLAMP_D
        cy_off = CLAMP_D / 2 if edge == "top" else -CLAMP_D / 2
        return Pos(cx_mm, cy_mm + cy_off, z_center) * Box(w_x, w_y, cut_h)
    # left / right
    w_x, w_y = CLAMP_D, CLAMP_W
    cx_off = CLAMP_D / 2 if edge == "left" else -CLAMP_D / 2
    return Pos(cx_mm + cx_off, cy_mm, z_center) * Box(w_x, w_y, cut_h)


def _base(x_min_mm, x_max_mm):
    width = x_max_mm - x_min_mm
    cx = (x_min_mm + x_max_mm) / 2
    return Pos(cx, DECK_DEPTH / 2, BASE_T / 2) * Box(width, DECK_DEPTH, BASE_T)


def _envelope(x_min_mm, x_max_mm):
    width = x_max_mm - x_min_mm
    cx = (x_min_mm + x_max_mm) / 2
    h = BASE_T + LIP_H + 1  # tall enough for 5 mm base + 2 mm lip
    return Pos(cx, DECK_DEPTH / 2, h / 2) * Box(width, DECK_DEPTH, h)


def _half(x_min_mm, x_max_mm):
    body = _base(x_min_mm, x_max_mm)
    for cx, cy, ly, sx in _SLOTS:
        if x_min_mm <= cx <= x_max_mm:
            body = body + _slot_lip(cx, cy, ly, sx)
            body = body - _slot_hole(cx, cy, ly, sx)
    for cx, cy, edge in CLAMP_POSITIONS:
        if x_min_mm <= cx <= x_max_mm:
            body = body - _clamp_pocket(cx, cy, edge)
    return body & _envelope(x_min_mm, x_max_mm)


def build_deck_plate_left():
    """Left half (X=0..100): used-tips bin + 96-well plate slots."""
    return _half(0.0, SPLIT_X)


def build_deck_plate_right():
    """Right half (X=100..219.8): tip-box + reservoir slots."""
    return _half(SPLIT_X, DECK_WIDTH)


def build_deck_plate_assembly():
    """Both halves combined into one part for visualisation.

    Origin (0, 0, 0) at the 96-well plate slot's left-front corner.
    Axis convention: +X right, +Y bed BACK (away from operator), +Z up
    — standard CAD top-down view. The Marlin frame's +Y points FRONT
    (toward operator), the opposite, so after translating we mirror Y.

    Resulting view layout (top-down +Z, +Y up):
      - Used-tips bin       back-LEFT (high +Y, overhangs -X)
      - Tip box             back-RIGHT
      - 96-well plate       extends from origin into +X, +Y
      - Reservoir           front-RIGHT (low +Y, high +X)
    """
    combined = build_deck_plate_left() + build_deck_plate_right()
    home_x = WELL_X - WELL_SHORT / 2  # = 10, well-plate left edge (Marlin frame)
    home_y = WELL_Y + WELL_LONG / 2  # = 232.3, well-plate front edge
    translated = Pos(-home_x, -home_y, 0) * combined
    return mirror(translated, about=Plane.XZ)


if __name__ == "__main__":
    export_part(build_deck_plate_left(), "labware", "deck_plate_left")
    export_part(build_deck_plate_right(), "labware", "deck_plate_right")
    export_part(build_deck_plate_assembly(), "labware", "deck_plate_assembly")
