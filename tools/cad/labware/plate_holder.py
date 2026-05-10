"""96-well plate holder with alignment pins.

SBS/ANSI standard footprint: 127.76 x 85.48 mm.
Reference: https://en.wikipedia.org/wiki/Microplate#Standards

Usage:
    uv run --extra cad python tools/cad/labware/plate_holder.py
"""

import sys
from pathlib import Path

from build123d import Box, Cylinder, Pos

sys.path.append(str(Path(__file__).resolve().parent.parent))
from util.export import export_part

sys.path.pop()

# --- Parameters (all in mm) ---
PLATE_LENGTH = 127.76  # SBS standard
PLATE_WIDTH = 85.48
PLATE_HEIGHT = 14.35

WALL_THICKNESS = 2.0
BASE_THICKNESS = 3.0
HOLDER_CLEARANCE = 0.5
PIN_DIAMETER = 3.0
PIN_HEIGHT = 5.0
PIN_INSET = 5.0

INNER_LENGTH = PLATE_LENGTH + HOLDER_CLEARANCE * 2
INNER_WIDTH = PLATE_WIDTH + HOLDER_CLEARANCE * 2
OUTER_LENGTH = INNER_LENGTH + WALL_THICKNESS * 2
OUTER_WIDTH = INNER_WIDTH + WALL_THICKNESS * 2
WALL_HEIGHT = PLATE_HEIGHT * 0.6


def _base_with_pocket():
    """Base plate with inner pocket cut (1mm floor preserved)."""
    holder = Pos(0, 0, BASE_THICKNESS / 2) * Box(
        OUTER_LENGTH, OUTER_WIDTH, BASE_THICKNESS
    )
    pocket_depth = BASE_THICKNESS - 1.0
    pocket = Pos(0, 0, BASE_THICKNESS - pocket_depth / 2) * Box(
        INNER_LENGTH, INNER_WIDTH, pocket_depth
    )
    return holder - pocket


def _walls():
    """Hollow rectangular walls atop the base."""
    walls = Pos(0, 0, BASE_THICKNESS + WALL_HEIGHT / 2) * Box(
        OUTER_LENGTH, OUTER_WIDTH, WALL_HEIGHT
    )
    inner_cut = Pos(0, 0, BASE_THICKNESS + WALL_HEIGHT / 2) * Box(
        INNER_LENGTH, INNER_WIDTH, WALL_HEIGHT + 1
    )
    return walls - inner_cut


def _alignment_pins():
    """Four alignment pins inset from inner-pocket corners."""
    positions = [
        (INNER_LENGTH / 2 - PIN_INSET, INNER_WIDTH / 2 - PIN_INSET),
        (-INNER_LENGTH / 2 + PIN_INSET, INNER_WIDTH / 2 - PIN_INSET),
        (INNER_LENGTH / 2 - PIN_INSET, -INNER_WIDTH / 2 + PIN_INSET),
        (-INNER_LENGTH / 2 + PIN_INSET, -INNER_WIDTH / 2 + PIN_INSET),
    ]
    pins = None
    for x, y in positions:
        pin = Pos(x, y, BASE_THICKNESS + PIN_HEIGHT / 2) * Cylinder(
            PIN_DIAMETER / 2, PIN_HEIGHT
        )
        pins = pin if pins is None else pins + pin
    return pins


def build_plate_holder():
    """Build 96-well plate holder with alignment pins."""
    return _base_with_pocket() + _walls() + _alignment_pins()


if __name__ == "__main__":
    export_part(build_plate_holder(), "labware", "plate_holder")
