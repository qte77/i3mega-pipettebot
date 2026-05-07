---
title: "Well-origin calibration"
status: "DRAFT"
updated: "2026-05-07"
owner: "lambda biolab"
---

Every i3 Mega has slightly different X/Y home offsets, and a well plate
is mechanically taped to the bed — there is no idealized origin. Before
running [`examples/showcase_v0.py`](../examples/showcase_v0.py) you must
measure where well A1 actually is on **your** build and update the
hardcoded constants.

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
- A pipette tip in the dPette (visual reference only — no aspirate yet).

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

Then raise to the travel altitude:

```text
G1 Z40 F1200
```

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

Open [`examples/showcase_v0.py`](../examples/showcase_v0.py) and replace
the constants at the top:

```python
WELL_A1 = (X_FROM_M114, Y_FROM_M114, Z_FROM_M114)   # was (100.0, 100.0, 5.0)
WELL_B1 = (WELL_A1[0], WELL_A1[1] + 9.0, WELL_A1[2])
TRAVEL_Z = 40.0     # adjust if your dPette + tip is taller than 35 mm
```

Run [`make validate`](../Makefile) to make sure your edits still type-check
and pass formatting.

### 6. Sanity check

Re-run preflight, then run the showcase with **water in well A1** and an
empty B1:

```bash
python examples/preflight.py        # confirm ports + firmware
python examples/showcase_v0.py
```

Watch the first cycle carefully. If anything looks wrong, **kill power
to the printer** before debugging. The PC has no soft-limit enforcement
in v0.

## What is deferred

- A proper `deck.py` with `WellPlate96`, `TipRack`, and named slots
- An origin-probe routine (`G38.2`-style) that auto-finds A1
- Persistence to a JSON file so you do not edit `showcase_v0.py` every time
- Soft-limit `safety.py` module (`MIN_TRAVEL_Z`, `DISPENSE_Z_OFFSET`)

All tracked in [AGENT_REQUESTS.md](../AGENT_REQUESTS.md) and follow-up
issues.
