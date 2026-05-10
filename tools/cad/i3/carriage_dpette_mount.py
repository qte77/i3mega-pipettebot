"""i3 Mega print-head carriage → dPette barrel mount (STUB).

Status: PLACEHOLDER — real geometry deferred to a follow-up PR.

Until the AI3M carriage screw-pattern dimensions are measured (or
provided as a CAD reference), this file ships a labeled placeholder so
the manifest entry, test fixtures, and import paths can be wired up
without blocking the rest of the pipeline.

What's missing (track in AGENT_REQUESTS.md):
    - AI3M print-head carriage face screw pattern (M3 spacing, hole
      diameters, plate thickness)
    - Bowden / direct-drive variant detection (stock Titan-style)
    - Cable/Bowden tube clearance envelope
    - dPette+ barrel diameter at the clamp height (Ø32mm split-bore for
      8-channel; Ø20mm round for single-channel — see so101's
      cad/dpette/dpette_handle.py / dpette_multi_handle.py for the
      proven barrel geometry to extract)

Once dimensions land, this file becomes the real mount; `parts.json`
flips its status from `planned` to `active`.

Usage (post-stub):
    uv run --extra cad python tools/cad/i3/carriage_dpette_mount.py
"""

import sys
from pathlib import Path

from build123d import Box, Cylinder, Pos

sys.path.append(str(Path(__file__).resolve().parent.parent))
from util.export import export_part

sys.path.pop()

# --- Placeholder dimensions (NOT measured — replace in follow-up PR) ---
PLATE_X = 60.0  # TODO: measure carriage face width
PLATE_Y = 40.0  # TODO: measure carriage face height
PLATE_Z = 4.0  # TODO: confirm plate thickness for stiffness
BARREL_BORE_D = 20.0  # placeholder: dPette 7016 single-channel barrel


def build_carriage_dpette_mount():
    """STUB — flat plate with a circular bore for visual placeholder.

    Returns a build123d Solid so the manifest dispatcher and smoke
    tests see a non-empty shape. Geometry has no functional intent and
    must NOT be printed.
    """
    # Mass: ~10g PLA stub (volume ~8 cc * 1.24 g/cc) — placeholder only,
    # real mount target is <100g per i3-carriage-payload-budget rule.
    plate = Box(PLATE_X, PLATE_Y, PLATE_Z)
    bore = Cylinder(BARREL_BORE_D / 2, PLATE_Z + 1)
    return plate - Pos(0, 0, 0) * bore


if __name__ == "__main__":
    export_part(build_carriage_dpette_mount(), "i3", "carriage_dpette_mount")
