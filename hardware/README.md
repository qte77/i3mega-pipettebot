---
title: "Hardware: pipette mount"
status: "DRAFT v0 — UNVERIFIED ON HARDWARE"
updated: "2026-05-08"
owner: "lambda biolab"
---

# Pipette mount adapter

Bolts a DLAB dPette pipette onto the **L-shaped front bracket** of the
Anycubic i3 Mega's X-carriage. That bracket has a horizontal top flange
bolted UP into the X-carriage and a vertical face hanging DOWN with the
4 inner M3 holes (formerly used by the hot-end's heat-block). Our
adapter:

1. Bolts to the L's **vertical face** via the 4 inner M3 holes — the
   primary load path.
2. Adds a **top wrap-over** that rises along the back of the L's
   vertical face and folds back across the top of the L's horizontal
   flange — the secondary load path. This stabilizer turns the cantilever
   into a closed truss so the L can't pivot or twist when loaded with
   the pipette's mass at the front of the carriage.

The pipette body hangs vertically in a split-clamp positioned forward
of the carriage face, so the tip is in the bed coordinate frame.

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
| 4 | M3 × 12 mm socket-head screws | Mount the adapter to the carriage — reuse the originals if they're long enough |
| 4 | M3 washers | Spread load across the printed plate |
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

### 4. L-bracket geometry (for the top wrap-over)

The wrap-over flange that ties the mount back to the carriage needs
two L-bracket measurements:

```
                    │  X-carriage face (front)
                    │
                    │ ┌───────────────────────┐    ┐
                    │ │ L's horizontal flange │    │
                    │ │ (bolted up into       │    │
                    │ │  the carriage)        │    │
                    │ └───┬───────────────────┤    │
                    │     │                   │    │
                    │     │                   │    │ l_face_h
                    │     │ L's vertical      │    │ (this height)
                    │     │ face — has 4      │    │
                    │     │ inner M3 holes    │    │
                    │     │                   │    │
                    │     └───────────────────┘    ┘
                          ↑                  ↑
                          back               front
                          (carriage          (forward)
                           side)
                          ←— wrap_depth_y →

```

- `l_face_h` — height of the L's vertical face from where it joins
  the horizontal flange down to its bottom edge. Measure with
  calipers or a ruler. **Default 55 mm.** Critical: too tall and
  the wrap riser collides with the L's bottom; too short and the
  wrap doesn't reach the L's top.

- `wrap_depth_y` — how far the wrap's horizontal arm extends back
  across the top of the L's horizontal flange. Should not extend
  past the carriage face itself or it'll collide with the gantry
  rails. **Default 22 mm.**

Optional: enable a single M3 through-hole in the wrap (`wrap_bolt_d`
= 3.4) so a longer M3 bolt can pass through the wrap, the L's top
flange, and into the carriage's mounting plate above for a positive
mechanical lock (eliminates any reliance on the wrap's printed
contact area). You'll need to confirm a usable hole on the carriage
side first; not all i3 Mega revisions have one in the right place.

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
