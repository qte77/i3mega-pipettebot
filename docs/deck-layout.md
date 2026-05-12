---
title: "Deck layout"
status: "DRAFT"
updated: "2026-05-13"
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
Y=220  |                                  ● TIP PICKUP           |  (X=155, Y=217.5)
       |                                                         |
Y=200  |                                                         |
Y=190  | ● SBS col 1  (X=50, Y=190)  ← cycle 1                   |
       | ●  col 2..4 (Y=181, 172, 163)                           |
Y=154  | ● col 5 (Y=154)                                         |
       | ●  col 6..7 (Y=145, 136)                                |
Y=115  | ●  col 8 (Y=127)             ● RESERVOIR (X=155, Y=115) |
       | ●  col 9..10 (Y=118, 109)                               |
       |                                                         |
  Y=100| ● col 11 (Y=100)            ← cycle 11 (last dispense)  |
       |                                                         |
    50 |                                                         |
       |                                                         |
       |                                                         |
Y=0    +---------------------------------------------------------+
                         BACK (Y=0)   ← G28 home corner
       X=0         X=50                        X=155          X=220
```

## Anchor points

The tour visits four named XY positions plus a home corner. Each is
specified in the Marlin frame (positive 0–250 Y convention). The
deck-frame slot extents that earlier iterations tried to track are
no longer authoritative — the user gave direct Marlin-Y anchors to
override them.

| Anchor | Marlin X | Marlin Y | Transit Z | Dive Z |
|---|---|---|---|---|
| Home / park | 0 | 0 | 95 | 74.25 (PARK_Z) |
| Reservoir aspirate | **155** | **115** | 95 (TRAVEL_Z) | **70** |
| SBS col 1 (first dispense) | **50** | **190** | 95 (TRAVEL_Z) | **70** |
| SBS col 11 (last dispense) | 50 | **100** | 95 (TRAVEL_Z) | 70 |
| Tip pickup TO leg (no tips) | **155** | **217.5** | 90 (TIP_PICKUP_PRE_Z) | **70** (engagement) |
| Tip pickup FROM leg (tips loaded) | **155** | **217.5** | 130 (TIP_PICKUP_LIFT_Z) | — (lifts away) |

SBS pitch is **−9 mm/cycle** (standard SBS column pitch; Y decreases each
visit). **11-cycle** ladder: **190, 181, 172, 163, 154, 145, 136, 127,
118, 109, 100**.

Tip-box loaded-tips height: **≥ 65 mm** (minimum — `TIP_PICKUP_PRE_Z`
and `TIP_PICKUP_LIFT_Z` are derived from this; if a taller tip box is
introduced, raise both first).

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
| `TRAVEL_Z` | **95** | Transit altitude — all inter-slot XY motion happens here. Clears SBS plate (top Z=13) by 82 mm, reservoir rim (Z=24) by 71 mm. The column tour never crosses the tip box (tip box Y=217.5 vs SBS Y_max=190), so the 30 mm clearance over the 65 mm loaded-tip-box minimum is informational only — phase 2 handles tip-box transit at `TIP_PICKUP_PRE_Z`/`LIFT_Z` |
| `WELL_Z` | **70** | Dive Z into SBS well; **invariant `WELL_Z ≥ RESERVOIR_Z`** (equality here) |
| `RESERVOIR_Z` | **70** | Dive Z into reservoir |
| `TIP_PICKUP_PRE_Z` | **90** | TO-leg approach Z (no tips on yet): body bottom is the lowest physical point, so 25 mm body clearance over the 65 mm tip box is enough |
| `TIP_PICKUP_Z` | **70** | Engagement Z; body bottom on tip tops |
| `TIP_PICKUP_LIFT_Z` | **130** | FROM-leg post-engagement lift (tips loaded): tip ends extend 49.5 mm below the body, so this sits 40 mm higher than PRE_Z to keep tip ends clear of the tip box (65 mm tip-end clearance) |
| `TIP_PICKUP_X` | 130 (slot pre-offset) → **155 (Marlin)** | Per user spec (shared with reservoir X) |
| `TIP_PICKUP_Y` | 217.5 (slot pre-offset) → **217.5 (Marlin)** | Per user spec |
| `RESERVOIR_REF_X` | 130 (slot pre-offset) → **155 (Marlin)** | Per user spec (shared with tip pickup X) |
| `RESERVOIR_REF_Y` | 115 (slot pre-offset) → **115 (Marlin)** | Per user spec |
| `SBS_REF_X` | 25 (slot pre-offset) → **50 (Marlin)** | Per user spec |
| `SBS_COL1_Y` | 190 (slot pre-offset) → **190 (Marlin)** | Cycle 1 dispense Y per user spec. Step −9 mm per cycle; 11-cycle ladder 190, 181, …, 100 |
| `SBS_COL_PITCH` | **−9 mm** | Standard SBS column pitch. Step between consecutive cycle Y positions (Y decreases each visit) |
| `M211 S0` (sent at bootstrap) | — | Disables Marlin software endstops defensively in case any commanded Y falls outside the firmware-configured Y_MIN/Y_MAX. Lasts until power-cycle |
| `PARK_Z` | **74.25** | End-of-tour park altitude. `1.5 × 49.5 mm` (disposable tip length) — clears any forgotten tip with half its length to spare |

> ℹ **Z-first transit pattern** (collision-safe): every slot visit
> follows `G1 Z=TRAVEL_Z` → `G1 X Y` → `G1 Z=dive` → `G1 Z=TRAVEL_Z`.
> XY motion ALWAYS happens at `TRAVEL_Z=95`, which is above every
> slot the column tour visits (SBS plate Z=13, reservoir Z=24). The
> tip box (Z=65 loaded) is not crossed by the column tour. The
> combined `G1 X Y Z` form is avoided. `visit_reservoir` and
> `visit_column` both delegate to a single `_visit_xy_dive(x, y, dive_z)`
> helper differing only in target XY and dive Z.

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
   `G28 X Y Z` (explicit axes — plain `G28` skips Z on this firmware).
   **No separate `G1 Z=TRAVEL_Z` lift** — phase 2's step 1 handles
   the post-G28 Z ascent directly. **Precondition: tips MUST be removed
   from the dPette before this phase**, because `Z=0` is calibrated to
   tip-end-on-deck (per [`calibration.md`](calibration.md)) — `G28 Z`
   would drive any mounted tip into the deck.
2. **Tip pickup** (once) — six-step Z-first sequence per user spec.
   Asymmetric pre/post: the TO leg (approach, no tips) ascends only
   to `TIP_PICKUP_PRE_Z=90` (body needs to clear the box), while the
   FROM leg (lift + reservoir transit, tips loaded) uses
   `TIP_PICKUP_LIFT_Z=130` (tip ends 49.5 mm below body need to
   clear the box).
   1. `G1 Z90` (ascend to TO-leg clearance — 25 mm body-bottom margin
      over the 65 mm loaded tip box).
   2. `G1 X155 Y217.5` at Z=90 (XY to tip box at TO-leg altitude).
   3. `G1 Z70` (engage tips — friction-fit, no plunger stroke).
   4. `G1 Z130` (lift with tips loaded — 65 mm tip-end margin over
      the tip box).
   5. `G1 X155 Y115` at Z=130 (travel to reservoir; X stays at 155,
      only Y moves — tip box and reservoir share X).
   6. `G1 Z95` (descend to `TRAVEL_Z`, hand off to cycle 1's Z-first
      transit pattern).
3. **Column tour** (11×) — for each SBS column N, in order 1..11, the
   `_visit_xy_dive` helper runs twice per cycle (once for reservoir,
   once for SBS column). Each call is the same 4-step Z-first sequence:
   1. `G1 Z=TRAVEL_Z` (lift to transit altitude).
   2. `G1 X Y` only, at TRAVEL_Z (no Z motion during XY).
   3. `G1 Z=dive_z` (descend — RESERVOIR_Z=70 for reservoir, WELL_Z=70
      for SBS column).
   4. `G1 Z=TRAVEL_Z` (lift back to transit altitude, ready for next).

   Cycle layout: reservoir at (155, 115); SBS columns at X=50,
   Y=190,181,…,100 (col 1 → col 11, −9 mm SBS pitch).
4. **Park at home corner** — Z-first sequence: `G1 Z=TRAVEL_Z` (no-op,
   already there) → `G1 X0 Y0` (XY at TRAVEL_Z) → `G1 Z=PARK_Z` where
   `PARK_Z = 1.5 × tip length = 74.25 mm`. Plain G1, not `G28` — trusts
   the tour's tracked position to save ~20 s of Z homing, and parks Z
   high enough to clear any tip still loaded on the dPette (forgotten-tip
   safety margin). Manually run `G28` afterwards if endstop re-reference
   is needed.

Column iteration steps `-9 mm` per cycle (standard SBS pitch; Y decreases each visit).
Cycle 1 lands at `Marlin Y = 190`, cycle 11 at `Y = 90`.

### Y motion timeline

Bed Y positions through the tour (back ↑ , front ↓), in Marlin frame:

```text
              Marlin Y (mm)   (Y=0 back, Y=250 front)
                 ↑ FRONT (operator)
   +250 ─────────│
   +220 ─────────●  tip pickup (Y=217.5, phase 2, once)
                 │
   +200 ─────────│
   +190 ─────────●  SBS col 1   ← phase 3 first dispense
                 │  SBS col 2..4 (181, 172, 163)
   +154 ─────────●  SBS col 5 (154)
                 │  SBS col 6..7 (145, 136)
   +127 ─────────●  SBS col 8 (Y=127)
   +118 ─────────●  SBS col 9 (closest to reservoir Y; 3 mm delta)
   +115 ─────────●  reservoir aspirate (every cycle)
   +109 ─────────●  SBS col 10 (closest to reservoir Y; -6 mm delta)
                 │
   +100 ─────────●  SBS col 11  ← phase 3 last dispense
                 │
    +50 ─────────│
                 │
                 │
      0 ─────────●  G28 home / phase 4 park / BACK of bed
                 ↓ BACK
```

Per-tour-cycle sequence:

```text
home(Y=0) → tip pickup(Y=217.5) →
  cycle 1:  reservoir(Y=115) → SBS col 1  (Y=190)
  cycle 2:  reservoir(Y=115) → SBS col 2  (Y=181)
  cycle 3:  reservoir(Y=115) → SBS col 3  (Y=172)
  cycle 4:  reservoir(Y=115) → SBS col 4  (Y=163)
  cycle 5:  reservoir(Y=115) → SBS col 5  (Y=154)
  cycle 6:  reservoir(Y=115) → SBS col 6  (Y=145)
  cycle 7:  reservoir(Y=115) → SBS col 7  (Y=136)
  cycle 8:  reservoir(Y=115) → SBS col 8  (Y=127)
  cycle 9:  reservoir(Y=115) → SBS col 9  (Y=118)
  cycle 10: reservoir(Y=115) → SBS col 10 (Y=109)
  cycle 11: reservoir(Y=115) → SBS col 11 (Y=100)
park(Y=0)
```

Bootstrap snippet:

```text
M203 Z20                     ; bump Z max feedrate cap (leadscrew limit)
M201 Z200                    ; bump Z max acceleration
M211 S0                      ; disable soft endstops (defensive)
G28 X Y Z                    ; home all axes — TIPS MUST BE REMOVED
M400
G1 Z95 F1200                 ; raise to TRAVEL_Z before any XY motion
M400
```

XY caps stay at firmware defaults; only Z is bumped because it's the
slow leadscrew axis and dominates per-cycle wall-clock.

`G28 X Y Z` (explicit axes — plain `G28` skips Z on the AI3M Marlin
variant) leaves the nozzle at the calibrated Z=0; the immediate Z
raise is mandatory before any XY motion, since the first motion
would otherwise drag any tip extension through near-home obstacles.

## Rationale

1. **Home corner is bed back** (Y=0). In the positive-Y convention,
   `G28` brings the bed all the way back; the dPette is over the rear
   of the deck at homed state.
2. **Reservoir at Y=115, SBS col 1 at Y=190** — both well within the
   0–250 Y range. Reservoir sits 75 mm back of SBS col 1, so the
   reservoir→col-1 transition is a single forward Y move.
3. **`TRAVEL_Z = 95`** = `WELL_Z + 25 mm` (25 mm transit margin above
   the reservoir/well dive Z). Reservoir↔SBS transit doesn't cross the
   tip box (tip box Y=217.5 vs SBS Y_max=190), so the 30 mm column-tour
   clearance over the 65 mm tip-box minimum is informational; phase 2
   handles tip-box transit at PRE_Z=90 / LIFT_Z=130. The previous
   125 mm transit altitude paid an extra 30 mm of Z stroke per dive (4
   per cycle × 30 mm = 120 mm/cycle), saving ~6 s per cycle at the
   Z_FEED=20 mm/s leadscrew cap.
4. **End with `G1` to home corner**, not `G28`. The tour does pure G1
   moves with no expected step loss, so a closing `G1 X0 Y0 Z PARK_Z`
   lands the carriage at the home corner ~20 s faster than re-homing
   every axis. Run `G28` manually if endstop re-reference is ever
   needed.
5. **`M211 S0` in the bootstrap** disables Marlin software endstops so
   commanded Y values aren't silently clamped to the firmware
   `Y_MIN`/`Y_MAX` range. With all current anchors in 0–220, this
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
3. **Tip-pickup Y placement** — anchored at Marlin Y=217.5 (front-right,
   shared X=155 with the reservoir). Confirmed against the physical
   tip-box position. Update `TIP_PICKUP_Y` if the deck rotates or the
   tip box moves.

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
