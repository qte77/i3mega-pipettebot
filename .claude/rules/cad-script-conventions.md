---
paths:
  - "tools/cad/**/*.py"
---

# CAD script conventions

## Each script exports `build_*()` functions

Files under `tools/cad/<area>/*.py` are loaded dynamically by
`tools/cad/render.py` via `parts.json`. The manifest names a `build_func`
per part — that function must exist as a top-level callable in the
referenced script.

**Rule**: every CAD script exposes one or more `build_*()` functions
that take no required arguments and return a `build123d.Solid`,
`build123d.Compound`, or an iterable of shapes that can be wrapped into
a Compound.

## No I/O, no prints, deterministic

`render.py` calls `build_*()` once per part and may cache the result.
Side effects (file writes, network, RNG) break caching and reproducibility.

**Rule**: CAD scripts must not:

- read or write files (rendering is `render.py`'s job)
- call `print` or log (the orchestrator handles output)
- use randomness or wall-clock time
- depend on environment variables

## Magic numbers carry units and rationale

All linear dimensions are in **mm**. Anything that looks like a magic
number (clearance, wall thickness, bore diameter) needs a one-line
comment with the source — measured value, datasheet reference, or SBS
labware spec.

**Rule**: numeric constants get a unit suffix in their name (`WALL_MM`,
`BORE_D_MM`) or a trailing comment naming the source.

## Assembly STLs: mirror Y after Marlin-frame translation

The Marlin frame and standard CAD top-down view point `+Y` in
**opposite directions**:

- Marlin (per `docs/deck-layout.md`): `Y=0` BACK, `Y=220` FRONT —
  `+Y` points TOWARD the operator.
- CAD top-down view (FreeCAD, PrusaSlicer, draw.io, ocp-vscode):
  `+Y` points AWAY from the viewer — the BACK of the part sits at
  high `+Y`.

A CAD assembly built directly from Marlin-frame constants therefore
looks mirrored front-to-back in any top-down viewer: labware meant
for the back of the bed shows up at the bottom of the screen.

**Rule**: any `build_*_assembly()` function (a part that combines
multiple sub-parts for visualisation) must apply a Y mirror **after**
the Marlin-frame translation:

```python
from build123d import Plane, Pos, mirror

def build_thing_assembly():
    combined = build_thing_left() + build_thing_right()
    translated = Pos(-home_x, -home_y, 0) * combined   # Marlin frame
    return mirror(translated, about=Plane.XZ)          # flip to viewer +Y BACK
```

Per-half / per-piece parts (intended for printing, e.g.
`build_deck_plate_left`) **do not** apply the mirror — the slicer
auto-orients them on the bed.

**Diagnostic**: STL bbox Y range comes out negative (e.g.
`Y[-232.30, -12.50]`) after Marlin-frame translation puts a corner at
the origin — that's the unmirrored Marlin view. After mirroring, Y
range is positive (`Y[12.50, 232.30]`).

See `AGENT_LEARNINGS.md` (2026-05-17 entry) for the bug occurrence
this rule was promoted from, and `tools/cad/labware/deck_plate.py`
for the canonical implementation.
