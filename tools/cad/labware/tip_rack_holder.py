"""Pipette tip rack holder — fixed workspace position.

Holds a standard 96-tip rack (SBS footprint variant). Universal across
SO-101, XZ-gantry, and i3 Mega contexts — pure deck geometry.

Usage:
    uv run --extra cad python tools/cad/labware/tip_rack_holder.py
"""

import sys
from pathlib import Path

from build123d import Box, Pos

sys.path.append(str(Path(__file__).resolve().parent.parent))
from util.export import export_part

sys.path.pop()

# --- Parameters (all in mm) ---
RACK_LENGTH = 122.0
RACK_WIDTH = 80.0
WALL_THICKNESS = 2.0
WALL_HEIGHT = 10.0
BASE_THICKNESS = 3.0
CLEARANCE = 0.5

INNER_L = RACK_LENGTH + CLEARANCE * 2
INNER_W = RACK_WIDTH + CLEARANCE * 2
OUTER_L = INNER_L + WALL_THICKNESS * 2
OUTER_W = INNER_W + WALL_THICKNESS * 2


def build_tip_rack_holder():
    """Build tip rack holder tray."""
    base = Box(OUTER_L, OUTER_W, BASE_THICKNESS)
    walls = Pos(0, 0, BASE_THICKNESS / 2 + WALL_HEIGHT / 2) * Box(OUTER_L, OUTER_W, WALL_HEIGHT)
    inner = Pos(0, 0, BASE_THICKNESS / 2 + WALL_HEIGHT / 2) * Box(INNER_L, INNER_W, WALL_HEIGHT + 1)
    return base + (walls - inner)


if __name__ == "__main__":
    export_part(build_tip_rack_holder(), "labware", "tip_rack_holder")
