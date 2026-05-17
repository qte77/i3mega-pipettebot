---
title: "3D parts: design rationale + labware reference"
status: "DRAFT"
updated: "2026-05-10"
owner: "lambda biolab"
---

Engineering reference for the parts under `tools/cad/`. The pipeline
itself (build123d → STL/SVG → OrcaSlicer printability gate) is described
in [AGENTS.md](../AGENTS.md) "3D Parts Pipeline" — this doc covers the
**why** behind the geometry: payload budget, Z envelope, labware standards.

Audience: anyone editing a `tools/cad/<area>/*.py` script and needing
to know what constraints the design must satisfy.

## Payload budget

> **Canonical rule: total carriage payload (mount + pipette + tips)
> must stay below 300 g.**

The stock Anycubic i3 Mega (AI3M) direct-drive carriage starts losing
steps under XY acceleration once payload exceeds ~300 g (empirical;
varies with belt tension and acceleration setting). All carriage-mounted
designs are sized against this single number.

Worked example for the dPette+ 8-channel target:

```text
budget   < 300 g
pipette  = 250 g  (dPette+ 8-channel; see hardware.md for source)
tips × 8 ≈   3 g  (300 µL polypropylene)
mount    < 300 − 250 − 3 = ~47 g
```

→ ~38 cc PLA volume budget for the mount (density 1.24 g/cc).
Practical implication: thin walls (1.5–2 mm), gyroid infill ≤ 20 %,
ribbed/triangulated stalks instead of solid blocks.

`.claude/rules/i3-carriage-payload-budget.md` enforces a `# Mass:`
annotation on every `build_*()` in `tools/cad/i3/`. Hypothesis tests
asserting `mount + pipette + tips < 300` are tracked in
[#42](https://github.com/qte77/i3mega-pipettebot/issues/42).

## Z envelope

i3 Mega is a bed-slinger: the **carriage moves only X+Z** (no Y), the
**bed moves Y**. The X-frame top sits 25 mm behind the carriage front
face and is therefore in a different spatial Y plane — it can never
collide with the pipette regardless of axis motion.

Vertical math, after stripping the print head:

```text
carriage face → bed (at Z_axis = 0)            : 19 mm
bed → X-frame top (full Z envelope)            : 290 mm
pipette tip → top (with 50 mm tip mounted)     : 280 mm
lower clamp → tip end                          : 150 mm
```

The 150 mm = 100 mm (clamp to bare body bottom) + 50 mm (tip extending
below the body).

Lower clamp sits at the carriage face level, so:

```text
tip Z = carriage_face_Z - 150 mm
```

For tip-at-bed (Z=0): `carriage_face_Z = 150 mm` → `Z_axis ≈ 131 mm`
(carriage face is 19 mm above bed at Z_axis=0).

**Usable Z range ≈ Z_axis 136 mm → 186 mm (~50 mm of pipetting travel)**
— enough for plate-to-plate work on labware up to ~25 mm tall. After
mount install, a tip-touch-off recalibration sets the new Z origin
(see [calibration.md](calibration.md)).

The pipette top can rise *above* the X-frame top in Z because they sit
in different Y planes — no upper Z bound from the X-frame. The dPette+
360° rotatable top adds extra angular clearance if needed.

## Mount geometry decisions

Two-clamp design:

- **Lower clamp** at carriage face level — split-bore 75 × 16 mm
  around the dPette+ body, above the ejector lever. Maximum mechanical
  stability (zero vertical lever arm to the screws).
- **Upper clamp** ≈ 100 mm above carriage face — Ø 27 mm round around
  the upper barrel. Prevents tilt under XY acceleration.

Forward projection: the lower clamp sits 15–25 mm in front (-Y) of the
carriage face so the pipette body clears the X-frame in spatial Y.
Constant in code (midpoint of the range, single source of truth):
`tools/cad/i3/carriage_dpette_mount.py::CLAMP_FORWARD_OFFSET_MM = 22.0`.

Open work: real geometry blocked on carriage measurements
([#40](https://github.com/qte77/i3mega-pipettebot/issues/40));
barrel-bore primitives extracted into a reusable module
([#41](https://github.com/qte77/i3mega-pipettebot/issues/41));
real scan vendored from so101
([#43](https://github.com/qte77/i3mega-pipettebot/issues/43)).

## SBS labware reference

Every `tools/cad/labware/` part conforms to the **SBS / ANSI-SLAS 2004-1
microplate footprint** (127.76 × 85.48 mm). This makes our holders
compatible with off-the-shelf labware from any manufacturer that
follows the standard.

| Labware | Footprint | Height | Notes |
|---|---|---|---|
| 96-well plate | 127.76 × 85.48 mm | ~14.35 mm | Modelled by `plate_holder.py` |
| Tip rack (96-tip variant) | ~122 × 80 mm | ~50 mm with tips | Modelled by `tip_rack_holder.py` |
| Reservoir, single-well V-bottom (100 mL) | 127.76 × 85.48 mm | ~30–40 mm | Bulk reagent for 8-channel — to be modelled |
| Reservoir, 8-channel divided (25 mL) | 127.76 × 85.48 mm | ~30 mm | Per-channel reagents — to be modelled |
| 8-channel-specific reservoir (e.g. MTC Bio ASPIR-8) | narrower than SBS | ~25 mm | Conserves bench space; optional |

Channel pitch for the dPette+ 8-channel matches SBS rows: **9.0 mm
centre-to-centre**, 8 channels span 63 mm.

Bed fixation of labware: deferred. v0 plan is binder clips at the
corners; a bed-adapter plate that snaps holders into known positions is
on the backlog.

## References

- [MTC Bio ASPIR-8 reagent reservoirs](https://www.thomassci.com/scientific-supplies/8-Channel-Reagent-Reservoirs) — 8-channel-specific reservoir, narrower than SBS
- [Multichannel pipette reservoir overview (Thomas Scientific)](https://www.thomassci.com/scientific-supplies/Multichannel-Pipette-Reservoir) — full SBS-footprint catalogue

dPette+ 8-channel product page is in [`hardware.md`](hardware.md).

## Open issues

| # | Topic |
|---|---|
| [#40](https://github.com/qte77/i3mega-pipettebot/issues/40) | Measure AI3M carriage screw pattern |
| [#41](https://github.com/qte77/i3mega-pipettebot/issues/41) | Extract barrel-bore primitives into reusable module |
| [#42](https://github.com/qte77/i3mega-pipettebot/issues/42) | Hypothesis tests for mount payload budget |
| [#43](https://github.com/qte77/i3mega-pipettebot/issues/43) | Vendor real dPette barrel scan |
| [#44](https://github.com/qte77/i3mega-pipettebot/issues/44) | Confirm OrcaSlicer install method |
| [#45](https://github.com/qte77/i3mega-pipettebot/issues/45) | ADR: Arduino host architecture |
