---
title: "Deck layout"
status: "DRAFT"
updated: "2026-05-11"
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

Coordinate convention: deck-plate frame, `X = 0` at the left edge, `Y = 0`
at the front edge of the deck plate, `Z = 0` at the deck-plate top surface.

**Marlin Y=0 is NOT the physical front of the bed** — it sits 175 mm
behind the physical front (per this printer's calibration). The bed
therefore has 175 mm of additional negative-Y travel past Marlin Y=0
before reaching its physical front limit. Negative Marlin Y values
that appear in this doc and the scripts (e.g. reservoir aspirate at
Y=−50, SBS col 12 at Y=−6) are all comfortably within reachable
travel.

## Top view

```text
Deck-frame physical layout (slot positions unchanged).
Bed movement adjustments are applied per-slot at runtime — see motion
constants table.

                              BACK  (Y = 220)
       +-----------------------------------------------------+
Y=220  |                                                     |
Y=207  | +-----------+                       +-----------+   |
       | |    SBS    | ← 44 mm corridor →    |  TIP BOX  |   |
       | |   plate   |    (X = 90 – 134)     |  (outer)  |   |
       | | 85 × 127  |                       | 81 × 120  |   |
       | | H = 13    |                       | H ≥ 59    |   |
       | | 12 col→Y  |                       | inner     |   |
       | |  8 row→X  |                       | 73.7×110  |   |
Y=100  | |           |                       +-----------+   |  Y=200
Y= 93  | +-----------+                                       |
       |       ↕ 27 mm (SBS → reservoir Y gap)               |
       |       ↕ 27 mm (tip box → reservoir Y gap)           |
Y= 53  |     +-------------------------------+               |
       |     |   RESERVOIR  134 × 43         |               |
       |     |   rim  Z = 24                 |               |
       |     |   floor Z = 19  (cavity 5)    |               |
Y= 10  |     +-------------------------------+               |
Y=  0  +-----------------------------------------------------+
         X=0  X=5    X=43          X=90  X=134      X=177  X=215  X=220
                              FRONT  (Y = 0)
         ↑ G28 lands nozzle here
         ← bed adjustments: SBS −100 mm, reservoir aspirate at Y=−50
```

## Slot extents

| Slot | X (mm) | Y (mm) | H (mm) | Footprint |
|---|---|---|---|---|
| SBS plate (back-left) | 5 – 90 | **80 – 207** | 13 | 85 × 127, 12 col → Y, 8 row → X; front edge 80 mm from bed front (physical position). Bed-movement adjustment: −100 mm applied when visiting SBS columns (see motion constants) |
| Tip box outer (back-right) | 134 – 215 | **80 – 200** | **≥ 59** | 81 × 120 (incl. loaded tips); front edge 80 mm from bed front |
| Tip box inner (tip array) | ~137.65 – 211.35 | ~85 – 195 | — | 73.7 × 110 |
| Reservoir (front, centered) | 43 – 177 | **10 – 53** | 24 (rim) / 19 (floor) | 134 × 43, length → X; cavity depth 5; front edge 10 mm from bed front |

All slots inset 5 mm from the nearest deck edge for handling tolerance,
mounting screws, and head-body clearance.

The tip-box height of **59 mm is the minimum** — that is the loaded-tips
height of the current box, and any tip box used on this deck must be no
taller. `TRAVEL_Z` is derived from this minimum (see below); if a taller
box is ever introduced, `TRAVEL_Z` must be re-derived first.

### dPette geometry

For fixture-clearance reasoning: the loaded dPette+ 8-channel head extends
**54 mm below the carriage reference** (tip end to the bottom of the dPette
body where it meets the mount). Per [`calibration.md`](calibration.md),
`Z = 0` in Marlin is calibrated to **tip-on-deck**, so the `Z` values in
this doc are tip-end altitudes and do *not* need a 54 mm offset added.
The 54 mm matters when designing CAD parts that might foul the dPette
body during XY travel.

## Free zones

| Zone | X (mm) | Y (mm) | Purpose |
|---|---|---|---|
| HOME pocket | 0 – 43 | 0 – 10 | `G28` landing area; no obstacle below nozzle |
| Travel corridor | 90 – 134 | 53 – 220 | Safe low-Z N-S route between back-row slots |
| Front-right pocket | 177 – 215 | 10 – 80 | Overflow access / future tool dock |
| Back-side gap (SBS / tip box → deck back) | 5 – 215 | 200 – 220 | 13–20 mm strip behind the back-row slots |

## Motion constants

Constants encoded in [`examples/showcase_v0_full_plate.py`](../examples/showcase_v0_full_plate.py):

| Constant | Value (mm) | Why |
|---|---|---|
| `DECK_OFFSET_X` | **+25** | Marlin commanded X = deck X + 25 (bed sits 2.5 cm right of nominal deck-frame plan) |
| `DECK_OFFSET_Y` | **−50** | Bed shifted another 5 cm forward on top of per-slot adjustments. Marlin Y=0 sits 175 mm behind physical front, so this stays well within reach |
| `TRAVEL_Z` | **125** | Bumped +50 from previous 75 ("Z OVERALL +5 cm"); clears tip box top (59 mm) by 66 mm |
| `RESERVOIR_Z` | **70** | Aspirate descent stop; 46 mm above 24 mm reservoir rim — no actual immersion |
| `WELL_Z` | **72** | Dispense descent stop; **invariant `WELL_Z ≥ RESERVOIR_Z`** — tip is never lower at dispense than at aspirate |
| `RESERVOIR_REF_Y` | 0 (slot pre-offset) → **-50 (Marlin)** | Aspirate at 5 cm behind Marlin Y=0 = 12.5 cm behind physical bed front. 125 mm of margin before the physical Y front limit (Y=-175) |
| `SBS_COL1_Y` | 193 (deck) → **43** (Marlin) | Back-most SBS column = first visit. Net shift = −100 (SBS-only bed shift) + −50 (global `DECK_OFFSET_Y`) = −150. Col 12 lands at Marlin Y=−56 — 119 mm before physical bed front limit |
| `TIP_PICKUP_X` | 142.5 (deck) → 167.5 (Marlin) | Outer-left of tip box (134) + 8.5 mm leftmost-tip-column offset |
| `TIP_PICKUP_Y` | 189.5 (deck) → **139.5** (Marlin) | Back-most tip column; minimizes Y travel into SBS column 1 |
| `TIP_PICKUP_Z` | **57** | Bumped +50; body-bottom at deck-Z 111 = 52 mm above 59 mm tip tops (no engagement; v0 sim) |
| `PARK_Z` | **74.25** | End-of-tour park altitude. `1.5 × 49.5 mm` (disposable tip length) — clears any forgotten tip with half its length to spare |

> ℹ **All descend points are now well above their slots** ("Z OVERALL
> +5 cm" applied globally). The tour exercises gantry XY motion at high
> Z without any actual immersion into the reservoir cavity or wells, and
> tip pickup no longer touches the tip tops. For real liquid handling,
> `RESERVOIR_Z`, `WELL_Z`, and `TIP_PICKUP_Z` must be re-derived against
> the actual slot geometry.
>
> ℹ **Aspirate Y = 0** means the bed sits against the Y front endstop
> during reservoir visits. Marlin will accept this exact coordinate but
> nothing below — the move is right at the mechanical limit.

Aspirate and dispense are each a **single descent** to the respective Z
(no up-and-back plunger stroke). The `WELL_Z ≥ RESERVOIR_Z` invariant
guarantees the tip is never deeper at dispense than at aspirate, which
also satisfies the motion-safety "tip above liquid before dispense" rule
([`../.claude/rules/motion-safety.md`](../.claude/rules/motion-safety.md)).

### Frame conventions

Slot extents (above) and motion targets are spec'd in the **deck-plate
frame** (`X = 0` at left edge, `Y = 0` at front). Marlin's frame is
offset from the deck frame by `(DECK_OFFSET_X, DECK_OFFSET_Y)` —
commanded coordinates in G-code are `deck_xy + offset`. The script
folds the offset into each XY constant at module load, so the G-code
stream is already in Marlin frame.

If the bed-vs-deck alignment changes (deck plate moved, bed
re-calibrated), only the two `DECK_OFFSET_*` constants need updating.

## Tour sequence

The full-plate tour ([`examples/showcase_v0_full_plate.py`](../examples/showcase_v0_full_plate.py))
runs in four phases (each phase is delimited by a `; ===== phase N =====`
comment in the tee'd G-code):

1. **Bootstrap** — full `G28`, then `G1` to `TRAVEL_Z`. **Precondition:
   tips MUST be removed from the dPette before this phase**, because
   `Z=0` is calibrated to tip-end-on-deck (per
   [`calibration.md`](calibration.md)) — `G28 Z` would drive any
   mounted tip into the deck. After homing, the Z raise lifts the
   carriage clear; tips are then picked up from the box in phase 2.
2. **Tip pickup** (once) — travel to `(TIP_PICKUP_X, TIP_PICKUP_Y, TRAVEL_Z)`,
   descend to `TIP_PICKUP_Z`, lift. No plunger stroke (pickup is a
   friction-fit, not a piston action).
3. **Column tour** (12×) — for each SBS column N, in order 1..12 (back
   → front):
   - Travel to reservoir at `TRAVEL_Z`, single descent to `RESERVOIR_Z`
     (aspirate), lift back to `TRAVEL_Z`.
   - Travel to plate column N at `TRAVEL_Z`, single descent to `WELL_Z`
     (dispense), lift back to `TRAVEL_Z`.
4. **Park at home corner** — `G1` to `(0, 0, PARK_Z)` where
   `PARK_Z = 1.5 × tip length = 74.25 mm`. Plain G1, not `G28` — trusts
   the tour's tracked position to save ~20 s of Z homing, and parks Z
   high enough to clear any tip still loaded on the dPette (forgotten-tip
   safety margin). Manually run `G28` afterwards if endstop re-reference
   is needed.

Column iteration is **back-to-front**: column 1 sits at `Y = 206`
(back-most, nearest the "top-left" of the plate per the deck spec) and
column 12 sits at `Y = 107` (front-most). Iteration step is `-9 mm` per
column.

### Y motion timeline

Bed Y positions through the tour (back ↑ , front ↓), in Marlin frame:

```text
              Marlin Y (mm)
                 ↑
   +220 ─────────│  bed back, mechanical limit-ish
                 │
                 │  tip box back  (TIP_PICKUP_Y = 139.5)  ← phase 2
   +100 ─────────│  ●
                 │
                 │
                 │  SBS col 1     (43)  ←  phase 3 first dispense
    +50 ─────────│  ●
                 │  SBS col 2..6  (34, 25, 16, 7, -2)
                 │
      0 ─────────●  G28 home / phase 4 park (Marlin Y=0)
                 │
                 │  SBS col 7..11 (-11, -20, -29, -38, -47)
                 │
    -50 ─────────●  reservoir aspirate (-50)        ← right above reservoir
                 │
                 │  SBS col 12    (-56)              ← phase 3 last dispense
                 │
   -100 ─────────│
                 │
                 │
   -175 ─────────│  PHYSICAL BED FRONT
                 ↓
```

Per-tour-cycle sequence:

```text
home(Y=0) → tip pickup(Y=139.5) →
  cycle 1:  reservoir(Y=-50) → SBS col 1  (Y=43)
  cycle 2:  reservoir(Y=-50) → SBS col 2  (Y=34)
  cycle 3:  reservoir(Y=-50) → SBS col 3  (Y=25)
  cycle 4:  reservoir(Y=-50) → SBS col 4  (Y=16)
  cycle 5:  reservoir(Y=-50) → SBS col 5  (Y=7)
  cycle 6:  reservoir(Y=-50) → SBS col 6  (Y=-2)
  cycle 7:  reservoir(Y=-50) → SBS col 7  (Y=-11)
  cycle 8:  reservoir(Y=-50) → SBS col 8  (Y=-20)
  cycle 9:  reservoir(Y=-50) → SBS col 9  (Y=-29)
  cycle 10: reservoir(Y=-50) → SBS col 10 (Y=-38)
  cycle 11: reservoir(Y=-50) → SBS col 11 (Y=-47)
  cycle 12: reservoir(Y=-50) → SBS col 12 (Y=-56)
park(Y=0)
```

Bootstrap snippet:

```text
G28                         ; home — nozzle to (0, 0, 0)
M400
G1 Z125 F1200               ; raise to TRAVEL_Z before any XY motion
M400
```

`G28` leaves the nozzle at the deck surface; the immediate Z raise is
mandatory before any XY motion, since the first motion would otherwise
drag any tip extension through near-home obstacles.

## Rationale

1. **Home corner stays clear.** Front-left `X < 43`, `Y < 10` has no
   slot; `G28` Z-probes against bare deck.
2. **Aspirate at Y = -50** is comfortably reachable: this printer's
   Marlin Y=0 sits 175 mm behind the physical bed front, so the bed
   has 125 mm of remaining forward travel at Y=-50. No soft-limit
   adjustment needed.
3. **Back row split** — SBS at `X = 5–90`, tip box at `X = 134–215` —
   leaves a 44 mm-wide travel corridor (`X = 90–134`) as the only N-S
   path that stays low-Z safe. Useful if `TRAVEL_Z` is ever reduced.
4. **`TRAVEL_Z = 125`** = previous 75 plus a global `+50 mm` ("Z OVERALL
   +5 cm" per user spec). Clears the 59 mm tip-box minimum by 66 mm.
   Every descend point (`RESERVOIR_Z`, `WELL_Z`, `TIP_PICKUP_Z`) also
   bumped +50; v0 sim no longer immerses into any slot.
5. **End with `G1` to home corner**, not `G28`. The tour does pure G1
   moves with no expected step loss, so a closing `G1 X0 Y0 Z75` lands
   the carriage at the home corner ~20 s faster than re-homing every
   axis. `I3MEGA_SKIP_HOME=1` similarly skips the start `G28` for
   back-to-back runs in the same session. Run `G28` manually if
   endstop re-reference is ever needed.

## Pipette orientation

The 8-channel dPette is mounted with its **8 channels aligned along X**.
The mount/carriage CAD under `tools/cad/i3/` is designed for this
orientation. Stepping A1 → A2 → … → A12 across a plate row is therefore
a Y-axis move (9 mm per column on the SBS pitch).

If the mount orientation is ever rotated 90° (8 channels along Y), the
SBS plate must rotate with it — the row axis must match the channel
axis.

## Open offsets

1. **Bed-vs-plate origin alignment** — resolved empirically as
   `DECK_OFFSET = (+25, −25)` (see [Motion constants](#motion-constants)
   "Frame conventions"). The deck plate sits 25 mm left and 25 mm back
   of the bed origin; the Marlin frame compensates by shifting +X / −Y.
   Re-derive if the deck plate is repositioned.
2. **Deck-plate thickness.** All `Z` values above are measured from the
   deck-plate **top** surface. If the plate is bolted on top of the
   heated bed (Marlin `Z = 0`), add the plate thickness to every `Z`
   constant.
3. **Channel-1 reach in X.** With SBS at deck `X = 5–90` and the 9 mm
   row pitch, channel 1's deck X target is ≈ 14 (Marlin X ≈ 39 after
   the `DECK_OFFSET_X`). If the dPette body fouls the X frame before
   reaching that Marlin X, shift the SBS right by the deficit and the
   tip box right by the same amount (preserves the 44 mm corridor).

These three are gating items for [`calibration.md`](calibration.md)
step 5 — record the measured values there.

## Related docs

- [`hardware.md`](hardware.md) — printer + pipette wiring, port
  disambiguation
- [`calibration.md`](calibration.md) — per-build well-A1 origin and
  dispense Z measurement
- [`3d-parts.md`](3d-parts.md) — carriage mount and Z-envelope math
- [`../.claude/rules/motion-safety.md`](../.claude/rules/motion-safety.md) —
  M400 sequencing, tip-above-liquid rule, soft-limit absence
