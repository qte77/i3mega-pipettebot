---
title: "Deck layout — ASCII sketch from showcase_v0_full_pipettebot_rows.py"
status: "DRAFT"
updated: "2026-05-17"
owner: "qte77"
---

ASCII top-down view derived from the constants in
[`examples/showcase_v0_full_pipettebot_rows.py`](../../examples/showcase_v0_full_pipettebot_rows.py).
Captures the geometry the row-tour script actually drives — anchor for
the eventual SVG version (tracked in the visualization-tool follow-up
issue).

i3 Mega bed = 210 × 210 mm. Y convention: Y=0 BACK, Y=220 FRONT
(measured envelope; differs from the older Y=250 figure in some doc
references — verify before relying on `MAX_NUM_CYCLES`-bound values).

## Top-down view

```text
                  ^ FRONT (operator side, Y=high)
       +------------------------------------------------+
Y=220  |                              [tip box row 12]  |  <- bed Y-max
       |                              | (Y=156+9*11=255 |     (warning: row 12 is
       |                              | -- WARNING:     |      outside Y=220 envelope!)
       |                              | outside bed)    |
       |                                                |
Y=210  |                              [tip box row 7]   |  (X=171, Y=210)
       |                              | rows step +9    |
Y=190  |  [bar] release approach (X=10)  |              |  bar: X=5, Y=190, Z=190
       |       engage (X=5, Y=190)        |             |  (oriented along Y)
Y=178  |                                                |
       |       [96-well row 12 max] (X=51, Y=178)       |
       |                                  |             |
Y=156  |       (plate footprint           [tip box row 1] (X=171, Y=156)
       |        X=51..~123,               |             |  rows step +9
       |        8 channels x 9mm)         |             |
Y=130  |                                  [reservoir    |  (X=171, Y=130)
       |                                  | transit Y]  |  (clear of tip-box edge)
Y=100  |                                  [reservoir    |  (X=171, Y=100)
       |                                  | aspirate]   |
Y=79   |       [96-well row 1] (X=51, Y=79)             |  start of dispense ladder
       |                                                |
       |                                                |
Y=10   |  [PARK_FINAL] (X=10, Y=10)                     |
Y=0    [HOME] (X=0, Y=0)                                |
       +------------------------------------------------+
       <- X=0    X=5            X=51..~123       X=171  X=210 ->
        (X-min)                                          (X-max)
                  v BACK (Y=0)
```

## Bar side view (X-Z, operator's perspective)

The release bar is a horizontal rod oriented along the Y axis.
Looking from the front (operator), Z up, X left-to-right:

```text
   Z ^                                                       (looking from FRONT, along -Y)
   ^
220 |                                                         <- bed Y-max (envelope edge)
    |                                                          (bar oriented along Y; cross-section here)
190 |  *  <- BAR cross-section (X=5, Z=190)
    |  |
    |  |     +----------------------------+
    |  |     |  dPette body (X=171 +/-~8, |
    |  |     |   Z extending ~280 mm      |
    |  |     |   below carriage when      |
    |  |     |   loaded with tips)        |
    |  |     |                            |
 98 |  *  <- carriage Marlin Z when hook engages bar
    |
  0 | ----------------------------------------------------  <- deck surface
    +----------------------------------------------------> X
      X=0  X=5            X=51                X=171  X=210
      |    bar             96-well            reservoir +  X-max
      HOME                 plate              tip box      frame
      <- LEFT (operator's left)              (operator's right) ->
```

## Discrepancies to verify before refreshing the doc

These are flagged from user-reported measurements vs script constants
— a calibration pass is queued as a follow-up:

1. **`RELEASE_BAR_X` / `RELEASE_BAR_Y`** were 0 / 220; corrected to 5 / 190
   in this PR per measured fixture. Other scripts using a release bar
   (`showcase_v0_tip_pickup_release.py`) may have similar drift —
   verify before running.
2. **Bed Y-max = 220**, not 250 (per user). The rows script's
   bed-range warning currently says "cycles 11-12 push past Y=250";
   real envelope means cycles 8+ are out (Y=156+9*7=219). Worth a
   `MAX_NUM_CYCLES` revisit (currently 12).
3. **Bar Z ≈ 190** vs the script's `RELEASE_ENGAGE_Z = 98`. Both can
   be true — the engagement Z is the gantry Marlin Z when the hook is
   under the bar; the bar's physical Z is 190 (hook + handle geometry
   bridges the ~92 mm gap). Worth a docstring clarification on the
   relationship.

## Key spatial relationships

- **X separation** between 96-well plate (X=51, channels extend to
  ~X=123) and tip-box / reservoir (X=171) gives ~50 mm clearance — no
  XY collision possible at travel altitude.
- **Y overlap** between tip box (Y=156..255) and plate (Y=79..178) in
  the Y=156..178 zone is OK because they're at different X.
- **Reservoir at Y=100** is between plate (max Y=178) and tip box (min
  Y=156), at the same X=171 as the tip box. The `_aspirate` helper
  does an intermediate `Y=130` move to clear the tip-box footprint
  before diving.
- **Release bar at Y=190** is between the 96-well plate and tip box
  rows, at the leftmost X. Approach at X=10 then slide to X=5 for
  engagement.
