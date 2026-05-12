---
title: "Deck layout"
status: "DRAFT"
updated: "2026-05-12"
owner: "lambda biolab"
---

Physical arrangement of labware on the 220 × 220 mm deck plate that sits
on the i3 Mega bed. The full-plate tour
([`examples/showcase_v0_full_plate.py`](../examples/showcase_v0_full_plate.py))
addresses this deck directly; the per-axis well-A1 origin and dispense Z
are still measured per-build in [`calibration.md`](calibration.md). The
older two-well demo
([`examples/showcase_v0_pipette_sim.py`](../examples/showcase_v0_pipette_sim.py))
predates this layout and uses its own hardcoded coordinates.

Coordinate convention: `X = 0` at the left edge, `Z = 0` at the
deck-plate top surface. Y axis is **positive 0–250 mm** (per this
printer's configuration): **Y=0 is the BACK** of the bed and **Y=250
is the FRONT**. Higher Y values move the bed toward the operator.
All Marlin-Y values in this doc and the scripts are positive.

## Top view

Anchor points only (Marlin frame, Y=0 back / Y=250 front). Slot
extents are no longer tracked in the deck-frame abstraction — the
tour uses absolute Marlin Y/X targets per the user-calibrated anchors.

```text
                       FRONT (operator, Y=250)
       +---------------------------------------------------------+
Y=250  |                                                         |
       |                                                         |
       |                                                         |
Y=200  |                                                         |
Y=180  | ● SBS col 1  (X=50, Y=180)  ← cycle 1                   |
       | ●  col 2..3 (Y=170, 160)                                |
Y=150  | ● col 4 (Y=150)           ● RESERVOIR  (X=160, Y=150)   |
       | ●  col 5..7 (Y=140, 130, 120)                           |
Y=139.5│                                       ● TIP PICKUP      |  (X=167.5)
       | ●  col 8..10 (Y=110, 100, 90)                           |
       |                                                         |
    Y=80| ● col 11 (Y=80)                                        |
    Y=70| ● col 12 (Y=70)            ← cycle 12 (last dispense)  |
       |                                                         |
    50 |                                                         |
       |                                                         |
       |                                                         |
Y=0    +---------------------------------------------------------+
                         BACK (Y=0)   ← G28 home corner
       X=0         X=50                   X=160  X=167.5     X=220
```

## Anchor points

The tour visits four named XY positions plus a home corner. Each is
specified in the Marlin frame (positive 0–250 Y convention). The
deck-frame slot extents that earlier iterations tried to track are
no longer authoritative — the user gave direct Marlin-Y anchors to
override them.

| Anchor | Marlin X | Marlin Y | Hover Z | Dive Z |
|---|---|---|---|---|
| Home / park | 0 | 0 | — | — |
| Reservoir aspirate | **160** | **150** | **105** | **75** |
| SBS col 1 (first dispense) | **50** | **180** | **85** | **75** |
| SBS col 12 (last dispense) | 50 | **70** | 85 | 75 |
| Tip pickup | **170** | **190** | 90 (pre) / 140 (lift) | **70** |

SBS pitch is **−10 mm/cycle** (Y decreases each visit). 12-cycle ladder:
**180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70**. Cycle 4
(Y=150) lands at the same Y as the reservoir, so that cycle's
reservoir→col transition is Z-only (no Y move).

Tip-box loaded-tips height: **≥ 59 mm** (minimum — `TRAVEL_Z` is
derived from this; if a taller tip box is introduced, raise `TRAVEL_Z`
first).

### dPette geometry

For fixture-clearance reasoning: the loaded dPette+ 8-channel head extends
**54 mm below the carriage reference** (tip end to the bottom of the dPette
body where it meets the mount). Per [`calibration.md`](calibration.md),
`Z = 0` in Marlin is calibrated to **tip-on-deck**, so the `Z` values in
this doc are tip-end altitudes and do *not* need a 54 mm offset added.
The 54 mm matters when designing CAD parts that might foul the dPette
body during XY travel.

## Motion constants

Constants encoded in [`examples/showcase_v0_full_plate.py`](../examples/showcase_v0_full_plate.py):

| Constant | Value (mm) | Why |
|---|---|---|
| `DECK_OFFSET_X` | **+25** | Marlin commanded X = deck X + 25 (bed sits 2.5 cm right of nominal deck-frame plan) |
| `DECK_OFFSET_Y` | **0** | Y convention is positive 0–250 (Y=0 back, Y=250 front); no offset needed |
| `TRAVEL_Z` | **125** | Post-`G28` raise altitude (above every slot) |
| `SBS_HOVER_Z` | **85** | Travel/lift Z when visiting SBS columns |
| `WELL_Z` | **75** | Dive Z into SBS well; **invariant `WELL_Z ≥ RESERVOIR_Z`** (equality here) |
| `RESERVOIR_HOVER_Z` | **105** | Travel/lift Z when visiting reservoir |
| `RESERVOIR_Z` | **75** | Dive Z into reservoir |
| `TIP_PICKUP_PRE_Z` | **90** | Defensive Z before XY travel to tip box (descended from `TRAVEL_Z`=125 to 90, still above tip box) |
| `TIP_PICKUP_Z` | **70** | Engagement Z; body bottom on tip tops |
| `TIP_PICKUP_LIFT_Z` | **140** | Post-engagement lift with tips loaded; clears tip box + tips |
| `TIP_PICKUP_X` | 145 (slot pre-offset) → **170 (Marlin)** | Per user spec |
| `TIP_PICKUP_Y` | 190 (slot pre-offset) → **190 (Marlin)** | Per user spec |
| `RESERVOIR_REF_X` | 135 (slot pre-offset) → **160 (Marlin)** | Per user spec |
| `RESERVOIR_REF_Y` | 150 (slot pre-offset) → **150 (Marlin)** | Per user spec |
| `SBS_REF_X` | 25 (slot pre-offset) → **50 (Marlin)** | Per user spec |
| `SBS_COL1_Y` | 180 (slot pre-offset) → **180 (Marlin)** | Cycle 1 dispense Y per user spec. Step −10 mm per cycle; 12-cycle ladder 180, 170, …, 70 |
| `SBS_COL_PITCH` | **−10 mm** | Step between consecutive cycle Y positions (Y decreases each visit) |
| `M211 S0` (sent at bootstrap) | — | Disables Marlin software endstops defensively in case any commanded Y falls outside the firmware-configured Y_MIN/Y_MAX. Lasts until power-cycle |
| `PARK_Z` | **74.25** | End-of-tour park altitude. `1.5 × 49.5 mm` (disposable tip length) — clears any forgotten tip with half its length to spare |

> ℹ Per-slot hover/dive scheme: each slot has its own hover Z used for
> travel and lift, and a dive Z for the descent. Z transitions between
> slots happen naturally during the next `G1 X Y Z` (no separate raise
> needed). SBS: hover 85 / dive 75. Reservoir: hover 105 / dive 75.

Aspirate and dispense are each a **single descent** to the respective Z
(no up-and-back plunger stroke). The `WELL_Z ≥ RESERVOIR_Z` invariant
guarantees the tip is never deeper at dispense than at aspirate, which
also satisfies the motion-safety "tip above liquid before dispense" rule
([`../.claude/rules/motion-safety.md`](../.claude/rules/motion-safety.md)).

### Frame conventions

Motion targets are spec'd in the **Marlin frame**: `X = 0` at the left
edge, `Y = 0` at the bed BACK, `Y = 250` at the bed FRONT (positive-Y
convention per this printer's calibration), `Z = 0` at the calibrated
tip-on-deck zero. The X axis still carries a `DECK_OFFSET_X = +25`
correction (legacy from when the deck-frame abstraction was active);
the Y axis has no offset (`DECK_OFFSET_Y = 0`).

If the bed-vs-deck alignment changes (deck plate moved, bed
re-calibrated), update the per-anchor Y values rather than introducing
a new global offset.

## Tour sequence

The full-plate tour ([`examples/showcase_v0_full_plate.py`](../examples/showcase_v0_full_plate.py))
runs in four phases (each phase is delimited by a `; ===== phase N =====`
comment in the tee'd G-code):

1. **Bootstrap** — `M203/M201` bump, `M211 S0` (disable software
   endstops so negative-Y reservoir/SBS targets aren't clamped),
   `G28 X Y Z` (explicit axes — plain `G28` skips Z on this firmware),
   then `G1` to `TRAVEL_Z`. **Precondition: tips MUST be removed from
   the dPette before this phase**, because `Z=0` is calibrated to
   tip-end-on-deck (per [`calibration.md`](calibration.md)) — `G28 Z`
   would drive any mounted tip into the deck. After homing, the Z
   raise lifts the carriage clear; tips are then picked up from the
   box in phase 2.
2. **Tip pickup** (once) — six-step sequence per user spec:
   1. `G1 Z90` (defensive pre-XY descent from `TRAVEL_Z=125`).
   2. `G1 X170 Y190` at Z=90 (travel to tip box).
   3. `G1 Z70` (engage tips — friction-fit, no plunger stroke).
   4. `G1 Z140` (lift with tips loaded — clears tip box + tips).
   5. `G1 X160 Y150` at Z=140 (travel to reservoir XY).
   6. `G1 Z105` (descend to `RESERVOIR_HOVER_Z`, hand off to cycle 1).
3. **Column tour** (12×) — for each SBS column N, in order 1..12:
   - Travel to reservoir (Marlin X=160, Y=150) at `RESERVOIR_HOVER_Z`
     (105), single descent to `RESERVOIR_Z` (75), lift back to
     `RESERVOIR_HOVER_Z`.
   - Travel to plate column N (Marlin X=50, Y=col_Y) at `SBS_HOVER_Z`
     (85), single descent to `WELL_Z` (75), lift back to `SBS_HOVER_Z`.
     Col 1 sits at Marlin Y=180; each subsequent column steps −10 mm
     in Y, so col 12 lands at Y=70.
4. **Park at home corner** — `G1` to `(0, 0, PARK_Z)` where
   `PARK_Z = 1.5 × tip length = 74.25 mm`. Plain G1, not `G28` — trusts
   the tour's tracked position to save ~20 s of Z homing, and parks Z
   high enough to clear any tip still loaded on the dPette (forgotten-tip
   safety margin). Manually run `G28` afterwards if endstop re-reference
   is needed.

Column iteration steps `-10 mm` per cycle (Y decreases each visit).
Cycle 1 lands at `Marlin Y = 180`, cycle 12 at `Y = 70`.

### Y motion timeline

Bed Y positions through the tour (back ↑ , front ↓), in Marlin frame:

```text
              Marlin Y (mm)   (Y=0 back, Y=250 front)
                 ↑ FRONT (operator)
   +250 ─────────│
                 │
                 │
   +200 ─────────│
   +180 ─────────●  SBS col 1   ← phase 3 first dispense
                 │  SBS col 2..3 (170, 160)
   +150 ─────────●  reservoir aspirate + SBS col 4 (same Y)
                 │  SBS col 5..10 (140, 130, 120, 110, 100, 90)
   +139.5 ───────●  tip pickup (phase 2, once)
   +100 ─────────│
                 │
                 │  SBS col 11..12 (80, 70)
    +70 ─────────●  SBS col 12  ← phase 3 last dispense
                 │
    +50 ─────────│
                 │
                 │
      0 ─────────●  G28 home / phase 4 park / BACK of bed
                 ↓ BACK
```

Per-tour-cycle sequence:

```text
home(Y=0) → tip pickup(Y=139.5) →
  cycle 1:  reservoir(Y=150) → SBS col 1  (Y=180)
  cycle 2:  reservoir(Y=150) → SBS col 2  (Y=170)
  cycle 3:  reservoir(Y=150) → SBS col 3  (Y=160)
  cycle 4:  reservoir(Y=150) → SBS col 4  (Y=150)  ← same Y as reservoir
  cycle 5:  reservoir(Y=150) → SBS col 5  (Y=140)
  cycle 6:  reservoir(Y=150) → SBS col 6  (Y=130)
  cycle 7:  reservoir(Y=150) → SBS col 7  (Y=120)
  cycle 8:  reservoir(Y=150) → SBS col 8  (Y=110)
  cycle 9:  reservoir(Y=150) → SBS col 9  (Y=100)
  cycle 10: reservoir(Y=150) → SBS col 10 (Y=90)
  cycle 11: reservoir(Y=150) → SBS col 11 (Y=80)
  cycle 12: reservoir(Y=150) → SBS col 12 (Y=70)
park(Y=0)
```

Bootstrap snippet:

```text
M203 X1000 Y1000 Z20        ; bump XY/Z max feedrate caps
M201 X2000 Y2000 Z200        ; bump XY/Z max acceleration
M211 S0                      ; disable soft endstops (defensive)
G28 X Y Z                    ; home all axes — TIPS MUST BE REMOVED
M400
G1 Z125 F1200                ; raise to TRAVEL_Z before any XY motion
M400
```

`G28 X Y Z` (explicit axes — plain `G28` skips Z on the AI3M Marlin
variant) leaves the nozzle at the calibrated Z=0; the immediate Z
raise is mandatory before any XY motion, since the first motion
would otherwise drag any tip extension through near-home obstacles.

## Rationale

1. **Home corner is bed back** (Y=0). In the positive-Y convention,
   `G28` brings the bed all the way back; the dPette is over the rear
   of the deck at homed state.
2. **Reservoir at Y=95, SBS col 1 at Y=125** — both well within the
   0–250 Y range. Reservoir sits 30 mm back of SBS col 1, so the
   reservoir→col-1 transition is a single forward Y move.
3. **`TRAVEL_Z = 125`** = previous 75 plus a global `+50 mm` ("Z OVERALL
   +5 cm" per user spec). Clears the 59 mm tip-box minimum by 66 mm.
   Every descend point (`RESERVOIR_Z`, `WELL_Z`, `TIP_PICKUP_Z`) also
   bumped +50; v0 sim no longer immerses into any slot.
4. **End with `G1` to home corner**, not `G28`. The tour does pure G1
   moves with no expected step loss, so a closing `G1 X0 Y0 Z PARK_Z`
   lands the carriage at the home corner ~20 s faster than re-homing
   every axis. Run `G28` manually if endstop re-reference is ever
   needed.
5. **`M211 S0` in the bootstrap** disables Marlin software endstops so
   commanded Y values aren't silently clamped to the firmware
   `Y_MIN`/`Y_MAX` range. With all current anchors in 0–140, this
   is precautionary; earlier iterations needed it because of negative
   Y commands.

## Pipette orientation

The 8-channel dPette is mounted with its **8 channels aligned along X**.
The mount/carriage CAD under `tools/cad/i3/` is designed for this
orientation. Stepping A1 → A2 → … → A12 across a plate row is therefore
a Y-axis move (9 mm per column on the SBS pitch).

If the mount orientation is ever rotated 90° (8 channels along Y), the
SBS plate must rotate with it — the row axis must match the channel
axis.

## Open offsets

1. **Bed origin alignment** — Y axis settled at no offset
   (`DECK_OFFSET_Y = 0`) once the positive-Y convention took over.
   X retains a `+25 mm` correction. Re-derive if the deck plate is
   repositioned or the printer's Y axis is reconfigured.
2. **Deck-plate thickness.** All `Z` values above are measured from
   the calibrated tip-on-deck zero. If the deck plate is repositioned
   in Z (e.g. mounted on a riser), every `Z` constant needs an offset
   added.
3. **Tip-pickup Y placement** — currently at Marlin Y=139.5, mid-bed.
   Verify against the physical tip-box position; if the tip box is at
   the bed back, `TIP_PICKUP_Y` should be much lower (close to Y=0).

These items belong in [`calibration.md`](calibration.md) step 5 once
the physical anchors are confirmed.

## Related docs

- [`hardware.md`](hardware.md) — printer + pipette wiring, port
  disambiguation
- [`calibration.md`](calibration.md) — per-build well-A1 origin and
  dispense Z measurement
- [`3d-parts.md`](3d-parts.md) — carriage mount and Z-envelope math
- [`../.claude/rules/motion-safety.md`](../.claude/rules/motion-safety.md) —
  M400 sequencing, tip-above-liquid rule, soft-limit absence
