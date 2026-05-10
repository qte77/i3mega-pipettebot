"""Rest cradles for AELAB dPette 7016 (single) and DLAB dPette+ (8-channel).

Holds pipette upright at known position when not on the i3 carriage.

Usage:
    uv run --extra cad python tools/cad/dpette/dpette_cradle.py
"""

import sys
from pathlib import Path

from build123d import Box, Cylinder, Pos

sys.path.append(str(Path(__file__).resolve().parent.parent))
from barrel_bore import make_clamp_bore
from util.export import export_part

sys.path.pop()

# --- Common parameters (all in mm) ---
WALL = 2.5
BASE_THICKNESS = 4.0
CRADLE_HEIGHT = 30.0
CLEARANCE = 0.5

# dPette 7016 single-channel barrel
SINGLE_BARREL_D = 20.0
SINGLE_OUTER_D = SINGLE_BARREL_D + CLEARANCE * 2 + WALL * 2

# dPette+ 8-channel body
MULTI_BODY_W = 50.0
MULTI_BODY_D = 25.0


def build_dpette_single_cradle():
    """Build rest cradle for dPette 7016 single-channel."""
    outer = Cylinder(SINGLE_OUTER_D / 2, CRADLE_HEIGHT)
    inner = Pos(0, 0, BASE_THICKNESS) * make_clamp_bore(
        SINGLE_BARREL_D, CRADLE_HEIGHT, diametral_clearance_mm=CLEARANCE * 2
    )
    cradle = outer - inner
    base = Box(SINGLE_OUTER_D + 10, SINGLE_OUTER_D + 10, BASE_THICKNESS)
    return base + Pos(0, 0, BASE_THICKNESS / 2) * cradle


def build_dpette_multi_cradle():
    """Build rest cradle for dPette+ 8-channel (must keep tips level)."""
    inner_w = MULTI_BODY_W + CLEARANCE * 2
    inner_d = MULTI_BODY_D + CLEARANCE * 2
    outer_w = inner_w + WALL * 2
    outer_d = inner_d + WALL * 2

    outer = Box(outer_w, outer_d, CRADLE_HEIGHT + BASE_THICKNESS)
    inner = Pos(0, 0, BASE_THICKNESS) * Box(inner_w, inner_d, CRADLE_HEIGHT + 1)
    cradle = outer - inner

    base = Box(outer_w + 20, outer_d + 20, BASE_THICKNESS)
    return base + Pos(0, 0, BASE_THICKNESS / 2) * cradle


if __name__ == "__main__":
    export_part(build_dpette_single_cradle(), "dpette", "dpette_single_cradle")
    export_part(build_dpette_multi_cradle(), "dpette", "dpette_multi_cradle")
