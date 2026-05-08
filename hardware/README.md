---
title: "Hardware: pipette mount"
status: "DRAFT v0 — UNVERIFIED ON HARDWARE"
updated: "2026-05-08"
owner: "lambda biolab"
---

# Pipette mount adapter

Bolts a DLAB dPette pipette onto the Anycubic i3 Mega's X-carriage
using **two attachment regions** so the pipette is supported by both
parts of the carriage assembly — not just the L bracket alone. The L
alone is a single point of failure: under the pipette's offset mass
the L would flex and twist. The adapter triangulates by anchoring to
*both*:

1. **Lower anchor — the L bracket's vertical face** via the 4 inner
   M3 holes (formerly the hot-end's heat-block mounts).
2. **Upper anchor — the carriage body's top face** via 2 corner M3
   holes (the screws visible at the upper-left/upper-right of the
   carriage's top plate in reference photos). A back riser climbs
   from the lower anchor up past the L and the carriage's vertical
   face; a top arm folds back across the carriage's top to land on
   those 2 corner holes.

The pipette body hangs vertically in a split-clamp positioned forward
of the carriage face, supported by a forward bridge from the lower
mount plate. With both anchors in place the load path is a closed
two-point truss — the pipette no longer hangs off a single
attachment.

```
                    │ X-carriage
                    │
                    │ ┌─────────────┐ ← top arm bolts here
                    │ │  ○      ○   │   (2 corner M3 holes)
                    │ ├──┬──────────┤
                    │ ░  │
                    │ ░  │ ← back riser (passes behind both L and
                    │ ░  │   carriage vertical faces)
                    │ ░  │
                    │ ┌──┴──────────┐
                    │ │ ▒ ◯  ◯  ▒  │ ← lower mount plate bolts to
                    │ │ ▒ ◯  ◯  ▒  │   L's 4 inner M3 holes
                    │ └─────┬───────┘
                    │       │ ↓ forward bridge
                    │       │
                    │       ┌──────┐
                    │       │clamp │ ← split-clamp grips dPette body
                    │       │  ⬭  │
                    │       └──────┘
```

> **Status: v0 draft.** This file has **not** been printed and
> verified against a physical i3 Mega yet. Treat the dimensions as
> starting points — measure your unit, edit the parameters at the
> top of [`pipette_mount.scad`](pipette_mount.scad), re-render, and
> iterate. See "Measurement workflow" below.

The design philosophy mirrors the modular bolt-on adapters used in
[lerobot's SO-101 / SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100):
single 3D-printed part, well-documented mounting hole pattern,
parametric source so end-users can adapt to their own hardware
without modeling from scratch.

## Files

| File | What it is |
|---|---|
| `pipette_mount.scad` | OpenSCAD source. Edit the parameters block at the top and regenerate. |
| `pipette_mount.stl`  | (not committed; regenerate per print) |

Generated STLs are not committed — they're easy to rebuild and bloat
the repo. Add them locally as `*.stl` for your slicer.

## Bill of materials

| Qty | Item | Notes |
|---:|---|---|
| 1 | 3D-printed `pipette_mount.scad` (PETG, ~25 g) | See print settings in the SCAD header |
| 4 | M3 × 12 mm socket-head screws | **Lower anchor** — reuse the originals if they're long enough |
| 2 | M3 × 12 mm socket-head screws | **Upper anchor** to the carriage's top corner holes |
| 6 | M3 washers | Spread load across the printed plate / top arm |
| 1 | M3 × 16 mm socket-head screw | Tightens the split clamp |
| 1 | M3 hex nut (DIN 934) | Captive in the clamp's nut pocket |

## Measurement workflow

The SCAD file has ~10 measured parameters at the top. They split into
three groups; verify each before printing.

### 1. Carriage hot-end mount pattern (most important)

The 4 inner M3 holes on the X-carriage's front plate. Visible in the
reference photos (`signal-2026-05-08-192633*.jpeg`) as the small
holes around the central hot-end bore.

```
                               ▲ (top of carriage)
              ┌──────────────────┐
              │  ○  ──vent──  ○  │  ← upper corner holes (don't use)
              │                  │
              │  □          □    │  ← inner M3 hot-end pattern
              │      ◯           │  ← central hot-end bore (relief
              │  □          □    │     in our adapter — `plate_relief_d`)
              └──────────────────┘
```

Measure with calipers between the centres of the **inner** square
holes (the `□` marks). On most stock i3 Mega carriages the spacing is
**~30 × 30 mm**, but verify because Anycubic shipped at least two
revisions of this plate. Update:

```openscad
mount_pattern_w = 30.0;   // horizontal spacing between hole centres
mount_pattern_h = 30.0;   // vertical spacing
```

### 2. dPette barrel diameter

Use calipers on the cylindrical grip section about 5 cm down from
the operation button — that's where the clamp will sit. Add 0.5-1 mm
to give the bore some slop (the dPette body has subtle ergonomic
curves that aren't a perfect circle):

```openscad
dpette_d = 32.0;          // OD at the clamp position; default 32 mm
```

If yours is markedly different, the SO-101-style split clamp adapts
fine — just change the value.

### 3. Vertical drop (`dpette_clamp_drop`)

This sets how far below the carriage plate the clamp hangs. Two
constraints:

- The dPette's tip should sit roughly where the original hot-end
  nozzle was, so the existing `Z=0` reference (bed-level) is unchanged.
  Measure from the clamp's planned mid-height to the dPette tip
  (`dpette_clamp_drop` + half of `dpette_clamp_h`).
- The clamp must not foul the gantry rails. With the printer at
  `Z=200` (top of travel), there should be at least 5 mm clearance
  between the top of the dPette and the X-axis gantry beam.

Default `35 mm` is a starting point that probably needs tweaking once
you've held the dPette next to the carriage.

### 4. Carriage geometry (for the back-brace + top anchor)

The dual-anchor stabilizer needs four carriage measurements:

```
                    │  Gantry rails (above)
                    │  ─────────────
                    │
                    │ ┌─────────────────┐  ┐
                    │ │  X-carriage     │  │ carriage_above_l_h
                    │ │   body          │  │ (height of carriage
                    │ │                 │  │  body above L's top)
                    │ │  ○         ○    │  │
                    │ └─┬───────────────┘  ┘   ← top corner holes here:
                    │   │                          their X-spacing is
                    │ ┌─┴───────────────┐  ┐       top_mount_pattern_w;
                    │ │ L horizontal     │  │       Y from carriage front
                    │ │  flange          │  │       face is top_mount_offset_y
                    │ ├──┬───────────────┤  │
                    │   │                   │ l_face_h
                    │   │ L vertical face   │ (height of L's
                    │   │ (4 inner M3 holes)│  vertical face)
                    │   │                   │
                    │   └───────────────────┘  ┘
                        ↑                ↑
                        back             front
                        (carriage        (forward)
                         side)
```

- `l_face_h` — height of the L's vertical face from where it joins
  the horizontal flange down to its bottom edge. Measure with
  calipers or a ruler. **Default 55 mm.**

- `carriage_above_l_h` — height of the carriage body above the L's
  top flange (measured from L's top up to the top surface of the
  carriage body where the corner mount screws live). **Default 25 mm.**
  Set to **0** to disable the upper anchor entirely (e.g. if your
  carriage has no usable top corner holes, or you want to print a
  shorter version for early bench testing).

- `top_mount_pattern_w` — X-axis spacing between the two corner
  mount holes on the carriage's top face. **Default 50 mm.**
  Measure with calipers between the two visible upper corner screws.

- `top_mount_offset_y` — how far back from the carriage's vertical
  face those corner holes sit. **Default 8 mm.** Determines where the
  top arm puts its M3 holes; getting this wrong by more than a
  millimetre will mean the bolts won't drop in cleanly.

The top arm extends `top_arm_y` back across the carriage's top
(default 30 mm). Make sure that depth doesn't foul the gantry rails
or any cable harness.

### Other tunables (less critical)

- `bridge_offset_y` — how far forward of the carriage face the clamp
  axis sits. Larger = pipette further from rails (good for clearance,
  bad for X-axis stiffness). Default 32 mm.
- `mount_hole_d` — clearance for M3. 3.4 mm if your screws fit
  reluctantly; 3.6 mm if you want easier alignment.
- `clamp_kerf` — width of the split. Wider kerf = more clamp travel
  but less clamping force. 1.6 mm is a good compromise.

## Iteration recipe

1. Measure the 3 mandatory parameters above.
2. Edit `pipette_mount.scad` parameters block.
3. Render-check in OpenSCAD: `openscad pipette_mount.scad` (F5
   preview, F6 full render).
4. Print a **first draft in PLA at 50% infill, 0.3 mm layer** — fast
   and cheap (~45 min). Check: do the 4 holes line up with the
   carriage? Does the clamp grip the pipette firmly?
5. Once geometry is right, re-print in PETG with the production
   settings in the SCAD header.
6. If clearance issues show up, capture a photo + the offending
   parameter and add to `AGENT_LEARNINGS.md` so v1 starts ahead.

## Known unknowns / open questions

These will be resolved as the design hits real hardware:

- Whether the L's 4 inner holes are M3 or M4 on every Anycubic
  revision (we assume M3).
- Whether the L's vertical face is recessed or flat — affects whether
  `plate_relief_d` is needed or if it should be 0.
- Whether the dPette's centre of mass on a 32-mm-forward bridge
  introduces enough sag *even with the wrap-over stabilizer* to
  require a third bracing point (e.g. a strut to the L's bottom
  holes if those exist as M3).
- Whether the cooling fan housing on the bottom of the carriage
  blocks the clamp at any Z position. May need a notch in the plate.
- Whether the wrap-over's horizontal arm collides with the X-carriage's
  upper structure when the carriage is at the back of its Y travel.
  Reduce `wrap_depth_y` if so.

## Companion firmware / software changes

This mount only handles physical attachment. To run the full pipette
workflow you also need:

- `M203 Z20` and `M201 Z200` to bump Z feedrate / accel — currently
  set in `examples/showcase_v0_pipette_sim.py` per power session.
- Path 3 (UART tap, see `docs/sbc-deployment.md`) if you want
  Marlin-driven `M820` aspirate/dispense from SD card instead of
  PC-as-host.
- Z-soft-limits will need updating once the dPette tip sits at a
  different Z than the original nozzle (`AGENT_REQUESTS.md` →
  Stage 1 firmware).
