"""dPette-only mirror of the 12-cycle reservoir→SBS tour — NO gantry motion.

Runs the same liquid-handling pattern as `showcase_v0_full_plate.py`
(12 reservoir aspirates + 12 SBS dispenses), but issues ONLY the dPette
serial commands. The i3 Mega is not opened, not homed, and not moved.

Use this to:
  - bench-test the dPette in isolation (no printer plugged in).
  - measure real B3 SUCK / B3 BLOW wall-clock times to replace the
    rough estimates baked into `showcase_v0_full_plate.py`.
  - dry-run the cycle-count budget (24 ops < MAX_CONTIGUOUS_CYCLES=50).

Sequence (12 cycles, each cycle = 1 aspirate + 1 dispense)::

    1. handshake     — DPetteDriver.connect() sends A0 HELLO, then B0
                       WOL to enter PI mode (motor homes).
    2. set volume    — B2 PI_VOLUM ONCE for the whole tour. Each cycle
                       reuses the same volume; no per-cycle B2 packet.
    3. tour          — for cycle in 1..12:
                         pipette.aspirate()   (B3 SUCK)
                         pipette.dispense()   (B3 BLOW)
    4. disconnect    — close the serial port.

Timing (approximate, replace after first real run):

  Modelled against the gantry F speeds in `showcase_v0_full_plate.py`:
  XY_FEED = 12000 mm/min (200 mm/s), Z_FEED = 1200 mm/min (20 mm/s).
  The dPette plunger stroke for a 100 uL aspirate is ~10 mm of mechanical
  travel; at a Z_FEED-equivalent 20 mm/s, that's ~0.5 s of motor time
  plus ~0.1 s ACK round-trip + ~0.1 s completion handshake.

  - B3 SUCK / B3 BLOW: ~0.4-0.8 s each (motor + 2x 6-byte serial RX).
    Driver's KEY_TIMEOUT_S = 10 s is the hard ceiling, not the typical.
  - Per cycle: ~1-2 s (aspirate + dispense back-to-back, no gantry).
  - Full 12-cycle tour: ~15-25 s wall-clock.

  For reference, the integrated tour in `showcase_v0_full_plate.py`
  spends ~11 s/cycle on gantry alone (4x ~55 mm Z descend/lift at
  20 mm/s + ~2x short XY at 200 mm/s), so the gantry is the bottleneck
  there — not the dPette.

Per-op and total elapsed seconds are printed to stdout. **No `M400`,
no `G1`, no Marlin port** — gantry-side ordering is the caller's
problem when this is composed with a real motion stack.

**Safety**: the B3 BLOW piston return creates suction. In a real run
the tip MUST be above the liquid surface before each dispense; this
script can't enforce that (no gantry), so only run it with the tip in
air or over a waste container.

Required environment variable:

    PIPETTE_PORT          dPette USB-serial path. Run `tools/preflight.py`
                          to discover it.

Optional:

    PIPETTE_BAUD          Default 9600 (DLAB dPette CP2102 stock).
    PIPETTE_VOLUME_UL     Per-channel volume in microlitres. Default 100.0.
"""

from __future__ import annotations

import os
import sys
import time

from dpette import DPetteDriver, SerialConfig

DEFAULT_BAUD = 9600
DEFAULT_VOLUME_UL = 100.0
NUM_CYCLES = 12


def _run_tour(pipette: DPetteDriver) -> None:
    """Issue 12 × (aspirate + dispense). Logs per-op timing."""
    tour_start = time.perf_counter()
    suck_total = 0.0
    blow_total = 0.0

    for cycle in range(1, NUM_CYCLES + 1):
        print(f"\n[dpette] ====== CYCLE {cycle}/{NUM_CYCLES} ======")

        t0 = time.perf_counter()
        pipette.aspirate()  # B3 SUCK (volume already set in main)
        dt_suck = time.perf_counter() - t0
        suck_total += dt_suck
        print(f"[dpette]   aspirate (B3 SUCK):  {dt_suck:.2f} s")

        t0 = time.perf_counter()
        pipette.dispense()  # B3 BLOW
        dt_blow = time.perf_counter() - t0
        blow_total += dt_blow
        print(f"[dpette]   dispense (B3 BLOW):  {dt_blow:.2f} s")

    tour_dt = time.perf_counter() - tour_start
    print(
        f"\n[dpette] tour done: {tour_dt:.1f} s total"
        f" ({suck_total:.1f} s in SUCK / {blow_total:.1f} s in BLOW)"
    )
    print(
        f"[dpette] averages: SUCK {suck_total / NUM_CYCLES:.2f} s,"
        f" BLOW {blow_total / NUM_CYCLES:.2f} s"
    )


def main() -> int:
    port = os.environ.get("PIPETTE_PORT")
    if not port:
        sys.stderr.write(
            "ERROR: set PIPETTE_PORT to the dPette's serial port.\n"
            "       Run `uv run tools/preflight.py` to discover it.\n"
        )
        return 1
    baud = int(os.environ.get("PIPETTE_BAUD", str(DEFAULT_BAUD)))
    volume_ul = float(os.environ.get("PIPETTE_VOLUME_UL", str(DEFAULT_VOLUME_UL)))

    print(f"[dpette] connecting on {port} @ {baud}")
    pipette = DPetteDriver(SerialConfig(port=port, baudrate=baud))
    pipette.connect()  # A0 HELLO → B0 WOL (PI mode) → motor homes
    if pipette.stub_mode:
        sys.stderr.write(
            f"ERROR: dPette on {port} fell back to stub mode.\n"
            "       Wake it (press its button), replug, and retry.\n"
        )
        return 1

    try:
        pipette.set_volume(volume_ul)  # B2 PI_VOLUM once; reused for all 24 ops
        print(f"[dpette] ready: PI mode, volume={volume_ul:.1f} uL per channel")
        _run_tour(pipette)
    finally:
        pipette.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
