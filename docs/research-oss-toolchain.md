---
title: "OSS toolchain research — firmware, slicers, alternatives"
status: "DRAFT"
updated: "2026-05-17"
owner: "qte77"
---

Research-grade reference for the OSS components this project depends on
(firmware + slicer + host tooling), the upstream-fork lineage of each,
and credible OSS alternatives if any dependency stalls. Sits orthogonal
to the operational docs:

- [`marlin-commands.md`](marlin-commands.md) — how to drive Marlin today.
- [`hardware.md`](hardware.md) — how to wire the printer and pipette.
- This doc — what these components are, who maintains them, and what
  to switch to if they stop being maintained.

Audience: anyone making a "should we keep / replace / fork X" call,
or auditing the project for OSS-license compatibility before publishing
a derived work.

Licenses below are as observed on each project's canonical (first-party)
repository on the `updated` date in the frontmatter — re-verify on the
upstream repo before relying on any of them for legal purposes.

## Snapshot — what runs today

| Component                | What we use                       | License    | Upstream / 1p URL                                              |
|--------------------------|-----------------------------------|------------|----------------------------------------------------------------|
| Motion firmware          | MARLIN-AI3M v1.4.6 (1.1.9 base)   | GPL-3.0    | <https://github.com/davidramiro/Marlin-AI3M>                     |
| Motion firmware (parent) | Marlin 1.1.x                      | GPL-3.0    | <https://marlinfw.org/>                                          |
| Slicer (primary)         | OrcaSlicer                        | AGPL-3.0   | <https://github.com/SoftFever/OrcaSlicer>                        |
| Slicer (fallback)        | PrusaSlicer                       | AGPL-3.0   | <https://github.com/prusa3d/PrusaSlicer>                         |
| Pipette driver           | dpette-usb-driver                 | (own repo) | <https://github.com/Lambda-Biolab/dpette-usb-driver>             |
| CAD                      | build123d                         | Apache-2.0 | <https://github.com/gumyr/build123d>                             |
| Host orchestrator        | pipettebot (this repo)            | (own repo) | <https://github.com/qte77/i3mega-pipettebot>                     |

Every entry above is OSS by intent — no closed-source link in the v0
stack. The "Future-proofing posture" section documents which components
are must-stay-OSS vs. OK-to-swap.

## The RepRap heritage

The entire stack above descends from the **RepRap project** (2005-),
started by Adrian Bowyer at the University of Bath as a self-replicating
desktop machine designed to be open by construction. Reprap.org is the
canonical wiki and project home:

- <https://reprap.org/wiki/Main_Page> — project home
- <https://reprap.org/wiki/Slicer> — survey of OSS slicers in the RepRap lineage

"reprap.com" exists as a UK reseller and partial wiki mirror — for
canonical project references always use **reprap.org**.

Lineage of the components we actually run:

```text
RepRap project (2005-)               https://reprap.org/
  Adrian Bowyer, Univ. of Bath       open hardware + software lineage
  |
  +-- Sprinter firmware (2011)       [archived]
  |     |
  |     +-- Marlin (2011-)           https://github.com/MarlinFirmware/Marlin
  |           Erik van der Zalm      GPL-3.0
  |           + community            https://marlinfw.org/
  |           |
  |           +-- Anycubic stock Marlin 1.4.x   (closed factory build, light mods)
  |           |
  |           +-- MARLIN-AI3M v1.4.6 (1.1.9)    https://github.com/davidramiro/Marlin-AI3M
  |                                              davidramiro, GPL-3.0
  |
  +-- Slic3r (2011-)                 https://github.com/slic3r/Slic3r
  |     Alessandro Ranellucci        AGPL-3.0
  |     |
  |     +-- PrusaSlicer (2016-)      https://github.com/prusa3d/PrusaSlicer
  |           Prusa Research         AGPL-3.0
  |           |
  |           +-- SuperSlicer        https://github.com/supermerill/SuperSlicer
  |           |     supermerill      AGPL-3.0
  |           |
  |           +-- Bambu Studio       (Bambu Lab fork of PrusaSlicer)
  |                 |
  |                 +-- OrcaSlicer   https://github.com/SoftFever/OrcaSlicer
  |                       SoftFever  AGPL-3.0
  |
  +-- RepRapPro Slicer (Java)        https://github.com/holgero/RepRapProSlicer
        holgero, GPL-family          https://reprap.org/wiki/RepRapPro_Slicer
        independent of Slic3r lineage
```

Why this matters: the GPL/AGPL anchor at every node means any firmware
patch we ship (e.g. the Stage 1 `M820` tap, see
[`sbc-deployment.md`](sbc-deployment.md) "What this doesn't unlock")
is a derivative work that must be released under the same license. The
project is positioned to honor that.

## Marlin firmware

Marlin is the motion brain on the i3 Mega. We use the community
**MARLIN-AI3M** variant specifically.

### Why MARLIN-AI3M, not stock or upstream

| Variant                | Why we don't use it                                                                       | Why MARLIN-AI3M wins                                                  |
|------------------------|-------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Anycubic stock 1.4.x   | Closed-ish factory build; weak community; EEPROM layout has drifted across factory revs.  | n/a                                                                   |
| Upstream Marlin 2.x    | Anycubic config + Trigorilla pin mapping isn't in the box; significant porting cost.      | n/a                                                                   |
| MARLIN-AI3M            | n/a                                                                                       | AI3M config in-tree; active community; EEPROM stable; Z probe + thermal-runaway already tuned for AI3M hardware. |

In v0 we run stock MARLIN-AI3M without modifications (see
[`hardware.md`](hardware.md)). Choice of variant matters for **future**
firmware work (Stage 1+), not for the current host-orchestrated workflow.

### Firmware alternatives worth tracking

| Alternative      | License  | 1p URL                              | When to consider                                                                                                                                                                                                |
|------------------|----------|-------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Klipper          | GPL-3.0  | <https://www.klipper3d.org/>          | Host-side motion planner — offloads compute from the ATmega2560. Input shaping, pressure advance, richer macros. Needs an always-on host (we already have one in Path 2; see [`sbc-deployment.md`](sbc-deployment.md)). |
| RepRapFirmware   | GPL-3.0  | <https://www.reprapfirmware.org/>     | Duet3D ecosystem. Only viable if we replace the Trigorilla board entirely (heavy refactor).                                                                                                                     |
| Smoothieware     | GPL-3.0  | <https://smoothieware.org/>           | LPC1768-based; doesn't run on the AI3M's AVR. Mainboard swap required.                                                                                                                                          |

For v0 and Stage 1 (firmware patch for `M820` pipette pass-through),
MARLIN-AI3M is the right answer. Klipper becomes interesting if input
shaping or richer macros enter scope.

## Slicers

We use the **OrcaSlicer / PrusaSlicer** pair (`tools/slicer/`) —
OrcaSlicer as primary, PrusaSlicer as fallback, both reading the same
`.ini` profile format from `tools/slicer/profiles/i3mega_*.ini`.

### Why OrcaSlicer + PrusaSlicer

- Shared `.ini` profile format — `tools/slicer/profiles/i3mega_*.ini`
  runs against both. Single source of truth per
  `.claude/rules/slicer-profile-source-of-truth.md`.
- Switching to PrusaSlicer if OrcaSlicer ever stalls is a one-line
  change in `tools/slicer/validate.py`.
- Both AGPL-3.0; license-compatible with our internal posture.

### Slicer alternatives

| Alternative           | License    | 1p URL                                       | Why we'd switch                                                                                              |
|-----------------------|------------|----------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| SuperSlicer           | AGPL-3.0   | <https://github.com/supermerill/SuperSlicer>    | Drop-in if PrusaSlicer drifts; same `.ini` format.                                                            |
| CuraEngine            | AGPL-3.0   | <https://github.com/Ultimaker/CuraEngine>       | Standalone engine — useful for slicer-as-library. Different profile format (incompatible with our `.ini`s).   |
| RepRapPro Slicer      | GPL-family | <https://github.com/holgero/RepRapProSlicer>    | Java, independent lineage. Niche; mostly relevant for RepRap-canonical builds.                                |
| Slic3r (legacy)       | AGPL-3.0   | <https://github.com/slic3r/Slic3r>              | The ancestor. Still alive but development pace is much slower than the PrusaSlicer fork.                      |
| reprap.org overview   | n/a (wiki) | <https://reprap.org/wiki/Slicer>                | Survey of the broader landscape (Skeinforge, KISSlicer, etc.) for reference.                                  |

For the printability gate (overhang / unsupported / bridge scan, per
`.claude/rules/cad-printability-gate.md`) all PrusaSlicer-lineage
slicers behave equivalently — the choice is operational (which one is
on the bench), not technical.

## Future-proofing posture

| Component            | Posture                                     | Why                                                                                                                                                  |
|----------------------|---------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------|
| Marlin family        | **Must stay OSS.** GPL-3.0 lineage protected. | We will likely need to patch firmware for the Stage 1 `M820` tap; vendor-lock would block this.                                                       |
| Slicer family        | **Must stay OSS.** AGPL-3.0 lineage protected. | Print profiles are tuned for the AI3M-with-stripped-head geometry — we need source access to add deck-aware safety checks if we ever go autonomous.   |
| dpette-usb-driver    | **Must stay OSS.** Our own.                 | Single source of truth for the dPette 6-byte protocol; bus factor = us.                                                                              |
| build123d            | Can swap if needed.                         | If build123d stalls, OpenSCAD (<https://openscad.org/>) or CadQuery (<https://github.com/CadQuery/cadquery>) are parametric fallbacks.                |
| Host orchestrator    | n/a (ours)                                  | n/a                                                                                                                                                  |

## Exit strategies

- **MARLIN-AI3M unmaintained** — port AI3M's config to upstream Marlin 2.x; medium effort. If the AVR is also dead, replace the Trigorilla board (SKR Mini / BTT clone) and use upstream Marlin 2.x directly.
- **OrcaSlicer unmaintained** — fall back to PrusaSlicer (already wired up in `tools/slicer/`); zero migration cost. Long-term, SuperSlicer is the next cousin.
- **PrusaSlicer relicensed** — pin to the last AGPL-3.0 release; promote SuperSlicer to primary fallback.
- **Both Slic3r-lineage slicers stall** — CuraEngine plus a custom profile translator. Significant work, but viable.
- **Escape Marlin entirely** — Klipper on the existing Path-2 Pi. Largest refactor; only justified if motion-planning richness becomes a bottleneck.

## Open questions

- dpette-usb-driver license — confirm and pin in the snapshot table once the upstream `LICENSE` is verified.
- Whether to vendor a checkpointed copy of MARLIN-AI3M source at the version we run, alongside `tools/cad/` and `tools/slicer/`, so a future fork-loss doesn't lock us out. Tracked as a future AGENT_REQUESTS.md item if we decide to.

## See also

- [`marlin-commands.md`](marlin-commands.md) — G/M-code reference for the Marlin family
- [`hardware.md`](hardware.md) — physical setup, firmware variant table, M115 sanity check
- [`calibration.md`](calibration.md) — Marlin Z=0 calibration after head removal
- [`3d-parts.md`](3d-parts.md) — CAD pipeline (build123d)
- [`sbc-deployment.md`](sbc-deployment.md) — Path 2 (SBC host), Path 3 (SD-card autonomy via firmware patch)
- [reprap.org wiki — slicer overview](https://reprap.org/wiki/Slicer)
- [reprap.org wiki — RepRapPro Slicer](https://reprap.org/wiki/RepRapPro_Slicer)
