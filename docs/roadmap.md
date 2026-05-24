# Roadmap

Forward-looking work — not exhaustive. Items here are either tracked
in [open GitHub issues](https://github.com/qte77/i3mega-pipettebot/issues)
(actionable now) or deferred to a future tagged milestone. Per
[CONTRIBUTING.md](../CONTRIBUTING.md) and AGENTS rule #4, anything that
modifies firmware needs an ADR before landing on `main`.

## Near-term (post-v0.1.0)

### Hardware bring-up

- **Geeetech A30 — Smartto motion-profile validation.** Live test
  observed FAST profile feeling slower than SLOW; suspected Smartto
  silently rejects M204/M201 values above some internal limit (research
  log "M400 race" already documents the ack-but-no-effect pattern).
  Need to probe with `tools/gantry_probe.py` at progressively larger
  values to find the ceiling, then either cap the profile range or
  re-anchor MID at a known-good value. May require ADR if MID changes.
- **A30 carriage payload measurement.** Unknown #5 in
  [`docs/research/gantry-firmware-alternatives.md`](research/gantry-firmware-alternatives.md).
  Without a number, the dPette + mount is operator-discretion. Needs a
  spring-scale or similar measurement, then a sibling rule to
  [`.claude/rules/i3-carriage-payload-budget.md`](../.claude/rules/i3-carriage-payload-budget.md)
  and a parallel CAD subtree at `tools/cad/a30/`.
- **A30 dPette mount + cradle CAD.** Once payload budget lands, design
  and print a carriage-mounted dPette holder for the A30. Counterpart
  to the i3 carriage mount under `tools/cad/i3/`.

### Library / tooling

- **Per-leg feedrate env overrides for the A30 showcase.** Currently
  `XY_FEED` / `Z_FAST_FEED` / `LIQUID_DIVE_FEED` / `TOUCHDOWN_APPROACH_MM`
  are Python constants. Adding env-var resolution with sane defaults
  (~6 lines) lets operators dial per-run without editing code, the
  same way `MOTION_PROFILE` works today.
- **M114-based motion-completion polling.** Current Smartto workaround
  is a 30 s host-side sleep before the post-cycle re-home. Polling
  `M114` until reported position stops changing would be more precise
  and could shorten the wait when the queue is shallow.
- **Branch-protection "Require signed commits".** CONTRIBUTING already
  documents the requirement; enabling the GitHub setting enforces it
  mechanically (currently honor-system at review time).

## Deferred to Stage 1+ (firmware track — needs ADR)

Per [README's PC-as-host architecture decision](../README.md#architecture-decision-why-pc-as-host-no-firmware-mods)
and AGENTS rule #4:

- **Stage 1 — Marlin config patch** for the i3 Mega. Tuned
  feedrate/accel/jerk floors, raised soft endstops, optionally an
  on-printer welcome banner.
- **Stage 2 — UART tap to dPette.** Direct firmware-side pipette
  command stream, eliminating the host-as-relay round-trip. Tracked in
  issues + the architecture-decision section of README.
- **Smartto firmware patches** (A30 family). `G28 Z` is broken on
  stock; ADR would need to cover the patched version + downstream
  delivery path before any merge.

## Deferred to a future API tier

From [docs/UserStory.md](UserStory.md) "Out of scope (v0)":

- **Deck calibration library** — typed deck-frame, slot-by-name
  addressing, calibration storage. Caller currently passes raw
  `(x, y, z)`.
- **Software soft-limit enforcement** — host-side coordinate
  validation before motion commands.
- **Multi-deck / multi-plate workflows** — currently single deck per
  session.
- **GUI** — Python API only for v0.

## Doc improvements

- **ADRs for the safe_home design** (0004) and **motion-profile 3x
  ratio retune** are in place; further design decisions get their own
  numbered ADR under `docs/adr/`.
- **Per-firmware operator guides** — Smartto/A30 has the research log
  plus ADR 0004; an i3-Mega counterpart guide would be symmetric.

## Anti-roadmap (won't do, even if asked)

- **Maintenance of a fork of Marlin** — stays upstream; patches go via
  ADRs and flashable artifacts, never as vendored submodules (license
  and maintenance overhead).
- **Re-encoding the dPette serial protocol in this repo** — see
  [`.claude/rules/pipette-delegation.md`](../.claude/rules/pipette-delegation.md).
  Always import `dpette.DPetteDriver`; never construct raw 6-byte packets.

## How items move on/off this list

- New work: open a GitHub issue first; the issue is the canonical
  tracker. Roadmap mentions the issue as a forward-look summary.
- Completed work: lands in CHANGELOG's Unreleased section, then in a
  tagged release entry. Removed from this roadmap when shipped.
- Withdrawn work: documented in the relevant research log or ADR with
  the rationale, then removed here.
