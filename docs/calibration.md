---
title: "Well-origin calibration"
status: "DRAFT"
updated: "2026-05-07"
owner: "lambda biolab"
---

Every i3 Mega has slightly different X/Y home offsets, and a well plate
is mechanically taped to the bed — there is no idealized origin. Before
running [`examples/showcase_v0_i3_pipette_sim.py`](../examples/showcase_v0_i3_pipette_sim.py)
you must measure where the back and front wells actually are on
**your** build and update the hardcoded constants.

In v0 calibration is a **manual edit-and-rerun** workflow. A proper
deck-frame library with persisted JSON calibration is in
[AGENT_REQUESTS.md](../AGENT_REQUESTS.md) and tracked as a follow-up
issue.

## Pre-requisites

- Hardware setup done — see [`hardware.md`](hardware.md).
- A 96-well plate (SBS footprint, 9 mm well-to-well pitch) physically
  taped to the bed. Long axis (12 columns) parallel to **X**; short axis
  (8 rows) parallel to **Y**. Row A nearest the printer's front.
- A G-code REPL: [pronterface](https://www.pronterface.com/) or any
  terminal that speaks Marlin (e.g. `screen /dev/ttyUSB0 115200`).
- A tip on **channel 1** of the dPette+ 8-channel head (leftmost
  channel — visual reference only, no aspirate yet).
- **Z origin re-calibrated** — see "Post-strip Z re-cal" below.

## Post-strip Z re-cal (dPette mount installed)

"Post-strip" = after the print head + PCB are removed and the dPette
mount is bolted onto the bare carriage (see [`hardware.md`](hardware.md)
"Workspace constraints").

Stock Marlin's Z=0 was calibrated to nozzle-touching-bed. With the
hotend gone, that reference no longer corresponds to anything useful:
the carriage face sits ~19 mm above the bed at Z_axis=0, and the
dPette tip with a 300 µL tip mounted hangs ~150 mm below the carriage
face. See [`3d-parts.md`](3d-parts.md) for the Z-envelope math.

One-shot tip-touch-off procedure:

1. Mount the dPette in the carriage and load a tip on **channel 1**
   (leftmost channel of the 8-channel head).
2. Place a sheet of paper flat on the bed under the tip.
3. Home: `G28`. Read baseline: `M114`.
4. Jog Z down slowly until the tip just kisses the paper — the paper
   should drag with light resistance under the tip:

    ```text
    G91
    G1 Z-5 F600
    G1 Z-1 F300
    G1 Z-0.1 F60
    ...
    G90
    M114
    ```

5. Set this Z as the new origin: `G92 Z0` (live override) and/or
   `M428` (tell Marlin "current position = home for current axes").
   `G92 Z0` is sufficient for v0 since the value isn't persisted across
   power cycles.
6. Lift to a safe travel altitude before any XY motion: `G1 Z40 F1200`.

The tip-touch Z value is the new reference for `WELL_Z` in
`examples/showcase_v0_i3_pipette_sim.py`. Add ~5 mm so the tip doesn't
crash into the well bottom on every cycle.

Re-run this procedure whenever you swap pipettes (single-channel ↔
8-channel) or change the tip volume class — different tips have
different lengths.

## Step-by-step

### 1. Home

```text
G28
```

After homing, Marlin reports `0,0,0` for X/Y and the configured Z
endstop position. **Read this baseline with `M114`** and write it down:

```text
M114
> X:0.00 Y:0.00 Z:0.00 E:0.00 Count X:0 Y:0 Z:0
```

### 2. Position over well A1

Jog X/Y until the dPette tip is **centered over well A1** (the corner
nearest the printer's front-left). Jog in 5 mm steps until close, then
in 1 mm steps for fine alignment.

Pronterface: use the on-screen jog buttons. Manual G-code:

```text
G91         ; relative mode
G1 X10 F2400
G1 X-1 F600  ; fine
...
G90         ; back to absolute
M114        ; record current position
```

Note the X and Y values reported by `M114`. **These are your
`WELL_A1[0]` and `WELL_A1[1]`.**

### 3. Find the dispense Z

This **replaces** the post-strip tip-touch-off Z (which was on the bare
bed). Now you find the Z at which channel 1's tip enters well A1 to a
useful depth.

With X/Y locked over A1, jog Z down slowly until the tip just kisses the
bottom of well A1:

```text
G91
G1 Z-5 F600
G1 Z-1 F300
G1 Z-0.1 F60   ; finest step
...
G90
M114
```

Record this Z. Add a small clearance (~0.5–1 mm) so you do not crash
into the plate on every cycle. **This is your `WELL_A1[2]`.**

Raise to a travel altitude that clears the plate's top edge (typically
plate top + 20 mm; a 14 mm SBS plate → travel Z ≈ plate-bottom Z + 35
mm). The 40 mm default in the showcase script assumes a stock hotend
and **must be re-derived** for the dPette geometry — see
[`3d-parts.md`](3d-parts.md) Z-envelope section.

### 4. Verify the 9 mm pitch on B1

Now translate Y by exactly 9 mm and check that the tip is centered over
well B1:

```text
G91
G1 Y9 F600    ; row B is +Y from row A
G90
M114
```

If the tip is centered over B1, your plate is square. If it is offset,
the plate is rotated relative to X — re-tape and start over from step 2.

`WELL_B1` is `(WELL_A1[0], WELL_A1[1] + 9.0, WELL_A1[2])`.

### 5. Update the showcase script

Open [`examples/showcase_v0_i3_pipette_sim.py`](../examples/showcase_v0_i3_pipette_sim.py)
and replace the constants near the top:

```python
CENTER_X = X_FROM_M114        # was 105.0 (mid-bed default)
BACK_WELL_Y = Y_FROM_M114     # was 180.0
FRONT_WELL_Y = ...            # was 20.0 (or any Y with clear travel)
WELL_Z = Z_FROM_M114          # post-strip Z is in the ~131 mm range, NOT 5
TRAVEL_Z = WELL_Z + 35.0      # plate top + ~20 mm of margin
```

Run [`make validate`](../Makefile) to make sure your edits still type-check
and pass formatting.

### 6. Sanity check

Re-run preflight, then run the showcase with **water in well A1** and an
empty B1:

```bash
uv run tools/preflight.py
uv run examples/showcase_v0_i3_pipette_sim.py
```

The first command confirms ports + firmware before motion.

Watch the first cycle carefully. If anything looks wrong, **kill power
to the printer** before debugging. The PC has no soft-limit enforcement
in v0.

## What is deferred

- A proper `deck.py` with `WellPlate96`, `TipRack`, and named slots
- An origin-probe routine (`G38.2`-style) that auto-finds A1
- Persistence to a JSON file so you do not edit `showcase_v0_i3_pipette_sim.py` every time
- Soft-limit `safety.py` module (`MIN_TRAVEL_Z`, `DISPENSE_Z_OFFSET`)

All tracked in [AGENT_REQUESTS.md](../AGENT_REQUESTS.md) and follow-up
issues.
