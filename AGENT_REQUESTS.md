# Agent Requests / Backlog

Strategic context for deferred-but-remembered work. This file holds the
*why* and area-level grouping; actionable state lives in GitHub issues.
No TODOs or closed-item history here — issue closure on GitHub is the
record.

## Liquid handling

v0 supports a single dPette+ on a fixed XY column. Multi-channel and
advanced operations are deferred until concrete protocols need them.
Related issues: [#8](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/8) (8-channel support — same driver, expose
`multichannel.COLUMN_PITCH_MM = 9.0`), [#9](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/9) (tip pickup / eject —
`dpette.eject_tip()` is `NotImplementedError`; needs GPIO solenoid or
M280 servo, depends on the Stage 1 firmware patch). Parallel-pipette
control, aspirate/dispense speed control surfaced through `PipetteBot`,
and mixing/splitting/dilution helpers are not yet issue-tracked —
delegate to `dpette.WorkingMode` when added.

## Deck and motion

Hardcoded `(x, y, z)` in v0; deck and calibration libraries are
deferred. Related issues: [#10](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/10) (`deck.py` with `WellPlate96`,
`TipRack`, named slots — blocked on a real multi-well protocol that
can't be expressed via the current `BACK_WELL_Y` / `FRONT_WELL_Y`
constants), [#11](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/11)
(`safety.py` with `MIN_TRAVEL_Z`, `DISPENSE_Z_OFFSET`). One-shot origin-probe / calibration
persisted to JSON, and trajectory-blending / look-ahead optimisation,
are not yet issue-tracked — current calibration flow is documented in
[`docs/calibration.md`](docs/calibration.md).

## Firmware (deferred from v0)

Stock Marlin only in v0; no firmware edits until an ADR lands. Related
issues: [#6](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/6)
and [#45](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/45)
(ADRs on PC-as-host vs Stage 2 integration and Arduino host architecture),
[#7](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/7) (Stage
1 — `Configuration.h` patch to disable thermal runaway on E0, raise
`Z_MAX_POS`, add `M280` for the tip-eject servo). Stage 2 work — pass-through
M-code (`M820`) for single-USB-cable mode, an embedded dPette state
machine for headless SD-card runs, and motion-planner-synchronous
pipetting for sub-50 ms sync — is not yet issue-tracked and probably
never needed for liquid handling.

## Hardware

The carriage mount STL ships now (scheme a + scheme b in
[`tools/cad/i3/carriage_dpette_mount.py`](tools/cad/i3/carriage_dpette_mount.py));
issue [#4](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/4)
tracks the remaining BOM. A 5 V ↔ 3.3 V level-shifter PCB for the Stage
2 UART tap is not yet issue-tracked; opens when Stage 2 work begins.

## 3D parts pipeline (`tools/cad/`)

Pipeline lives under [`tools/cad/`](tools/cad/), governed by
[`docs/3d-parts.md`](docs/3d-parts.md). Open issues:
[#43](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/43)
(vendor real dPette barrel scan from so101),
[#44](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/44)
(confirm OrcaSlicer install method on dev / CI),
[#45](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/45)
(ADR: Arduino host architecture).

## SBC deployment (Path 2)

Concrete follow-ups so [`docs/sbc-deployment.md`](docs/sbc-deployment.md)
can graduate from DRAFT: a first physical Pi-on-Mega build with photos
and confirmed BOM lines; a 3D-printed mount STL under
`hardware/sbc-mount.stl`; a power-piggyback test (24 V → 5 V buck off
the i3 Mega PSU, confirming clean enumeration of both USB-UART chips);
a CI matrix entry for `linux/arm64` (Pi Zero 2 W is `aarch64`); and an
audit of which deferred features fail on Pi Zero (RAM-limited) vs Pi 4
(comfortable). None yet issue-tracked.

## Tooling / quality

Issues: [#12](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/12)
(Hypothesis property-based tests for gantry framing),
[#13](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/13)
(coverage, `bump-my-version`, mkdocs).
[#26](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/26)
covers the `GcodeGantry._send` single-line-per-command bug. CodeFactor,
CodeQL, and Dependabot badges are not yet issue-tracked.

## Skills / automation deferred

Several Claude-Code skills are mapped to future work but not yet
useful: `embedded-dev:implementing-firmware` (waits on Stage 1+),
`docs-generator:generating-tech-spec` (next use case is an ADR on the
UART-tap decision), `cc-meta:orchestrating-parallel-workers` (when STL,
firmware, and multichannel land as a parallel build). A SessionStart
hook to auto-load motion-safety rules would surface them earlier in
context but isn't yet needed in practice.

## Documentation

Hardware setup ([`docs/hardware.md`](docs/hardware.md)) and calibration
([`docs/calibration.md`](docs/calibration.md)) docs ship; the preflight
script lives at [`tools/preflight.py`](tools/preflight.py). Remaining:
a hardware photo set (mount, plate, tips, dPette) for
`.github/assets/hero.png` ([#5](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/5)),
a demo video / GIF replacing the placeholder `.github/assets/showcase.gif`,
and the ADR explaining "PC-as-host instead of Stage 2 firmware
integration" ([#6](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/6)).

## Open assumptions to revisit

- v0 supports a **single dPette only**, hardcoded coordinates, no calibration library
- `dpette` consumed as a **git dep** pinned to a commit SHA (not vendored)
- Repo is **public** on GitHub
- `.claude/settings.json` has **no hooks** in v0
- `.claude/rules/` lives in-repo today; [ADR 0001](docs/adr/0001-repo-structure-alignment.md) decides this de-vendors to the marketplace plugin once the migration starts
