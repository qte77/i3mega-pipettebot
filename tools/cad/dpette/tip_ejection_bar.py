"""Tip ejection post — fixed post for mechanical tip removal.

The dPette/dPette+ uses a top-mounted push-button ejector. For robotic
automation the pipette is positioned so the ejector button presses DOWN
against this fixed post. The print head lowers Z onto the post,
activating the ejector; the tip falls through the waste hole in the base.

Usage:
    uv run --extra cad python tools/cad/dpette/tip_ejection_bar.py
"""

import sys
from pathlib import Path

from build123d import Box, Cone, Cylinder, Pos

sys.path.append(str(Path(__file__).resolve().parent.parent))
from util.export import export_part

sys.path.pop()

# --- Post (contacts ejector button) ---
POST_DIAMETER = 8.0
POST_HEIGHT = 60.0  # Must clear the tip + nozzle below the button
POST_TIP_RADIUS = 3.0

# --- Base plate ---
BASE_LENGTH = 60.0
BASE_WIDTH = 40.0
BASE_THICKNESS = 4.0

# --- Mounting ---
BOLT_HOLE_D = 4.2  # M4 clearance
BOLT_SPACING_X = 40.0
BOLT_SPACING_Y = 20.0

# --- Waste hole ---
WASTE_HOLE_D = 25.0


def _base_with_features():
    """Base plate with waste hole and 4x M4 mounting holes."""
    base = Box(BASE_LENGTH, BASE_WIDTH, BASE_THICKNESS) - Cylinder(
        WASTE_HOLE_D / 2, BASE_THICKNESS + 1
    )
    for bx in (-BOLT_SPACING_X / 2, BOLT_SPACING_X / 2):
        for by in (-BOLT_SPACING_Y / 2, BOLT_SPACING_Y / 2):
            base = base - Pos(bx, by, 0) * Cylinder(BOLT_HOLE_D / 2, BASE_THICKNESS + 1)
    return base


def build_tip_ejection_bar():
    """Build tip ejection post with base plate."""
    base = _base_with_features()
    post = Pos(0, 0, BASE_THICKNESS / 2) * Cylinder(POST_DIAMETER / 2, POST_HEIGHT)
    tip_cone = Pos(0, 0, BASE_THICKNESS / 2 + POST_HEIGHT) * Cone(
        POST_DIAMETER / 2, POST_TIP_RADIUS, POST_TIP_RADIUS * 2
    )
    return base + post + tip_cone


if __name__ == "__main__":
    export_part(build_tip_ejection_bar(), "dpette", "tip_ejection_bar")
