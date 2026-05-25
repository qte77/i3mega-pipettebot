# Tip disposal — research log

Append-only notes on getting used disposable tips off the deck and
into a waste vessel. v0 currently relies on
`tools/cad/dpette/dpette_tip_release.py` — an L-bracket ejector
station with a wide waste slot that releases the tip into whatever
container the operator places under the deck cutout. This log tracks
alternative mechanisms (active conveyance, multi-cycle harvesting)
and why none have been adopted yet.

## Evaluation criteria

Hard requirements for any candidate:

- Stock Marlin / Smartto compatibility — no spare stepper outputs
  are available on the printer mainboard, and firmware modification
  is out of scope per AGENTS rule #4.
- Sub-$150 build anchor preserved — any add-on hardware competes
  against the bare-bones build cost.
- No interference with the carriage payload budget
  ([`.claude/rules/i3-carriage-payload-budget.md`](../../.claude/rules/i3-carriage-payload-budget.md),
  i3 cap 300 g).

Soft preferences:

- Re-uses commodity parts (timing belt, NEMA17, generic stepper
  driver) so the BOM is sourceable from any 3D-printer scrap.
- Composes with the optional SO-101 companion (which currently
  handles used-tips *bin* retrieval, not continuous transport).

## Entries

### 2026-05-26 — Conveyor-belt 3D printer landscape

Surveyed in response to the question "could a conveyor-belt 3D
printer provide off-the-shelf belt geometry for tip transport?"

| Printer | Vendor | Price (USD) | Belt | Hackability |
|---|---|---|---|---|
| IdeaFormer IR3 | IdeaFormer | $499 | Roll-off, PU/polyester | Marlin-class |
| SainSmart INFI-20 | SainSmart | $849 | Roll-off, textured nylon | Marlin-class |
| iFactory One | iFactory3D | $999 | Roll-off, tilted | Semi-proprietary |
| Creality CR-30 3DPrintMill | Creality | $1,000–1,049 (vendor URL 302s to homepage — likely discontinued; secondary-market only) | Roll-off, 45° nylon | Marlin fork, well-modded |
| White Knight | [NAK3DDesigns / Carl][wk-gh] | ~$2,000 BOM (DIY) | Roll-off, BuildTak | GPL-3.0, fully open |
| Blackbelt 3D | Blackbelt 3D | $10,000–10,450 | Roll-off, adjustable 15–45° | Proprietary |

[wk-gh]: https://github.com/NAK3DDesigns/White-Knight

Sources: [3dsourced.com conveyor-belt roundup][3ds] (January 2024),
[clevercreations.org best-belt roundup][cc],
[3ddistributed.com MRRF-2019 White Knight writeup][3dd]. GitHub repo
metadata for White Knight (GPL-3.0, 351 stars, last push 2021-04-23)
verified via `gh api`.

[3ds]: https://www.3dsourced.com/3d-printers/conveyor-belt-3d-printer/
[cc]: https://clevercreations.org/best-conveyor-belt-3d-printer/
[3dd]: https://3ddistributed.com/mrrf-2019/white-knight-3d-printer/

- **Belt geometry finding:** All commercial conveyor-belt 3D
  printers use a **tilted roll-off** belt (typically 45°). No
  vendor sells a true horizontal-loop belt geometry. For tip
  transport this matters less than expected — a tilted roll-off
  would still carry tips off the end into a bin — but the
  "buy a belt printer, harvest the mechanism" path costs $499+
  and breaks the sub-$150 build anchor.
- **Earlier vendor attributions removed after verification:** BIQU
  sells no belt printer (full product line checked). Annex
  Engineering makes no belt printer either — all 34 of their repos
  are CoreXY designs. Both attributions appeared in an initial
  draft survey and were removed after vendor-side verification.

### 2026-05-26 — Standalone belt module (commodity BOM)

Considered as an alternative to harvesting a belt printer.

- **BOM (approximate):** GT2 6 mm closed-loop timing belt with 2× 20T
  pulleys ($10–22), NEMA17 stepper from printer scrap ($8–15), 2020
  aluminum extrusion frame ~300 mm ($8–15), TMC2209 or A4988 driver
  with Arduino Nano or RP2040 ($5–12), brackets and fasteners ($5–8)
  — **~$37–72 total**. Open-source reference geometry for stepper
  sizing and belt tensioner: `github.com/NAK3DDesigns/White-Knight`
  (GPL-3.0), with the explicit caveat that White Knight is
  tilted-belt, not horizontal — only the belt subsystem details
  carry over.
- **Integration blockers for v0:** The i3 Mega and A30 mainboards
  have no spare stepper output usable from stock Marlin / Smartto,
  and firmware modification is out of scope (AGENTS rule #4). The
  belt would need a separate microcontroller commanded over a
  second USB link from the host, plus a host-side mini-driver. That
  extra bus and extra firmware is out of scope for v0.
- **Verdict:** **DEFERRED.** v0 keeps the passive
  `dpette_tip_release` waste slot. An active belt is a real post-v0
  option for high-cycle workflows where the bin fills mid-run and
  the SO-101 companion isn't present, but it requires either Stage
  1+ firmware work (out of scope) or a parallel-MCU side path (out
  of scope without a concrete use case driving it).
