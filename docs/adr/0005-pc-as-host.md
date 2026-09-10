# ADR 0005: PC-as-host — no firmware modifications through v0

- **Status:** Accepted
- **Date:** 2026-09-09
- **Scope:** [qte77/i3mega-pipettebot](https://github.com/qte77/i3mega-pipettebot) only

## Context

Every supported gantry (Marlin/AI3M on the i3 Mega, Smartto on the A30)
ships stock. The PC drives motion over USB-serial and drives the dPette
over a second, independent USB-serial link — no wire, tap, or firmware
change connects the two devices to each other. `AGENTS.md` rule 4 already
states this as policy ("No firmware modifications in v0 — stock Marlin
only") without recording why, or what the rejected alternatives were. This
ADR formalizes that decision and lays out the staged path (Stage 1 → 2c)
that stays out of scope until a concrete need forces it.

Pipetting cycles are slow: seconds per gantry move, seconds per
aspirate/dispense. USB-serial round-trip latency (~20–50 ms per command) is
three orders of magnitude below the cycle time, so there is no throughput
or timing pressure pushing control logic onto the printer's own MCU.

## Decision

Stay on **Stage 0** through v0: stock firmware, PC orchestrates both
devices independently, no shared clock or shared bus between them. The
staged escalation path, for reference when a future requirement actually
demands it:

| Stage | Description | Trigger to consider it |
|---|---|---|
| **0 (current)** | Stock Marlin/Smartto, unmodified. PC opens two independent serial links (gantry + dPette) and sequences both from Python. | — (default; this ADR keeps v0 here) |
| **1** | `Configuration.h` patch only — e.g. a compiled-in feedrate/limit tuned for the removed print head's mass, no new runtime behavior. Still two independent links; PC still sequences. | A liquid-handling-relevant motion parameter can't be set at runtime (`M203`/`M201`/`M204`/`M205`, per [ADR 0003](./0003-motion-profile-bundled-constants.md)) and has no G-code equivalent. |
| **2a** | Pass-through M-code (custom `M820`-class command) forwarded from Marlin to the dPette over a UART tap. Requires a level-shifter (dPette UART is not 5V-tolerant against the printer board) and a firmware patch to relay bytes. | Round-trip latency between gantry and pipette actually matters — not observed at v0's cycle times. |
| **2b** | Embedded dPette state machine inside Marlin: pipetting commands become G-code the printer executes standalone, enabling headless SD-card runs with no PC in the loop. | A headless/untethered run mode becomes a real requirement (e.g. field deployment without a laptop). |
| **2c** | Motion-planner-synchronous pipetting — aspirate/dispense timed against the stepper planner for sub-50 ms sync. | Probably never needed for disposable-tip, gravity-assisted liquid handling; listed for completeness only. |

Each stage is strictly additive to the one before it and is its own future
ADR + `docs/research/` entry if pursued — this ADR does not pre-approve
any of Stage 1+, it only records where the line currently sits and why.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| **Stage 1 now** (compile-time Marlin config patch) | No current parameter needs it; every liquid-handling-relevant setting (`MOTION_PROFILE`'s M203/M201/M204/M205 bootstrap) is already runtime-settable over G-code. Patching firmware for a parameter that G-code already reaches would add a build/flash step for zero behavioral gain. |
| **Stage 2a now** (UART pass-through) | Requires new hardware (level-shifter) and a firmware fork per printer family (Marlin and Smartto would each need their own patch) for a latency problem that doesn't exist at pipetting-cycle timescales. |
| **Single MCU driving both gantry and pipette from one firmware image** | Would require reverse-engineering the dPette's control loop into Marlin/Smartto (well beyond a pass-through) and abandons `_Pipette`-Protocol pipette-agnosticism (`AGENTS.md` decision framework) — a new pipette model would need its own firmware fork instead of just a new driver class. |

## Consequences

### Pros

- **Zero firmware risk.** Stock firmware means no bricked boards, no
  per-printer-family firmware fork to maintain, and full compatibility
  with community Marlin/Smartto updates.
- **Two independent serial links stay independently testable.** The
  existing `FakeSerial`/`FakePipette` test doubles (`tests/conftest.py`)
  model this directly — nothing about Stage 0 requires hardware-in-loop
  testing infrastructure Stage 2 would need.
- **`_Pipette` Protocol stays firmware-agnostic.** Swapping pipette
  hardware only ever means a new driver behind the Protocol, never a
  firmware change.

### Cons

- **No headless/untethered run mode.** A PC (or SBC — see
  [`docs/sbc-deployment.md`](../sbc-deployment.md)) must be present and
  running for every pipetting run through v0.
- **Round-trip latency is paid on every command**, currently
  inconsequential but a real cost if per-command overhead ever needs to
  drop below tens of milliseconds.

### Neutral

- **Stage 1+ work is fully deferred, not blocked.** `AGENT_REQUESTS.md`
  and issues #7 (Marlin config patch) and #9 (tip-eject mechanism) already
  track Stage 1/2a candidates; per `AGENTS.md` rule 4 they require their
  own ADR before merging to `main`, which this ADR does not preempt.

## Out of scope

- **Choosing between Stage 2a/2b/2c** — each needs its own bring-up and
  ADR if a trigger condition above is actually met.
- **SBC-vs-PC as the host** — orthogonal to this decision; either can run
  the same Stage-0 two-link orchestration (see
  [`docs/sbc-deployment.md`](../sbc-deployment.md)).

## References

- `AGENTS.md` rule 4 — "No firmware modifications in v0. Stock Marlin
  only." This ADR is that rule's rationale record.
- Issue #6 — original request to document this decision.
- Issues #7, #9 — Stage 1/2a candidates, gated on this ADR existing.
- [ADR 0003](./0003-motion-profile-bundled-constants.md),
  [ADR 0004](./0004-printer-firmware-policy-and-safe-home.md) — sibling
  ADRs for the runtime-tunable motion path this decision keeps in Python,
  not firmware.
