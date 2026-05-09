---
paths:
  - "src/pipettebot/**"
  - "examples/**"
  - "tests/test_*.py"
---

# Motion safety

## Always wait for moves before pipetting

Marlin's planner queues G-code commands and continues accepting new ones
while motion is in progress. Sending an aspirate or dispense command
immediately after a `G1` move means the pipette fires while the gantry
is still in flight — wrong well, possibly mid-air.

**Rule**: between any `gantry.move_to(...)` and any pipette
`aspirate(...)` / `dispense(...)`, call `gantry.wait_for_moves()`
(M400) — or use `PipetteBot.aspirate_at()` / `dispense_at()` which do
this for you.

## Tip above liquid before dispense

dPette's B3 blow includes a piston return to home that creates suction.
If the tip is submerged when you dispense, this draws extra liquid and
ruins the volume.

**Rule**: raise Z to a travel altitude before any `dispense_at(...)` —
or design `move_to(...)` calls so the dispense Z is above the liquid
surface in that well.

## Stay within soft limits

v0 has no software soft-limit enforcement (deferred to AGENT_REQUESTS.md).
Treat all coordinates as untrusted: the i3 Mega will happily drive the
nozzle into the bed if asked.

**Rule**: every hardcoded coordinate in `examples/` and tests must have
a comment indicating the deck slot it represents.
