"""Solo-arm recorder — pose the arm by hand with torque off; capture joint stream.

No leader needed. Disables torque on every servo so the operator can pose the
arm physically, then sync-reads Present_Position at the loop rate and appends
JSONL lines compatible with `tools/teleop_replay.py`. Same recording format,
same per-servo sync_read fallback under mixed firmware.

Usage:
    uv run --extra teaching python tools/teleop_record.py \\
        --arm=/dev/ttyACM1 \\
        --record=captures/tip_box_solo.jsonl

Then replay onto the same (or a sibling) arm:

    uv run --extra teaching python tools/teleop_replay.py \\
        --follower=/dev/ttyACM1 \\
        --record=captures/tip_box_solo.jsonl

Torque stays off on Ctrl-C — the operator can keep moving the arm. The replay
script re-enables torque on its own startup so no manual step in between.

Caveat: servos sag under gravity with torque off (gripper especially). Static
keyframes are easy; fluid trajectories require holding the arm against gravity
throughout the motion.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import TYPE_CHECKING

from _teleop_common import (
    ADDR_PRESENT_POSITION,
    BAUD,
    SERVO_IDS,
    format_record_line,
    read_leader_positions,
    set_torque,
)

if TYPE_CHECKING:
    from typing import IO

DEFAULT_HZ = 60.0


def _record_loop(
    reader: object,
    packet: object,
    port: object,
    record_file: IO[str],
    rate_hz: float,
):  # type: ignore[no-untyped-def]
    """Read joint positions every period and append a JSONL line.

    Yields the 1-based tick index after each successful read so callers can
    show progress or terminate on a count. Ticks where both batch and per-
    servo fallback fail are skipped silently (no empty lines written).
    """
    period = 1.0 / rate_hz
    t0 = time.perf_counter()
    idx = 0
    while True:
        tick = time.perf_counter()
        positions = read_leader_positions(reader, packet, port)
        if positions:
            record_file.write(format_record_line(tick - t0, positions))
            idx += 1
            yield idx
        elapsed = time.perf_counter() - tick
        if elapsed < period:
            time.sleep(period - elapsed)


def main() -> int:
    """Record one arm's joint positions while torque is off."""
    parser = argparse.ArgumentParser(
        description=(
            "Solo-arm recorder — pose by hand (torque off), capture JSONL "
            "for later replay (no leader, no lerobot)."
        ),
    )
    parser.add_argument("--arm", required=True, help="arm serial port path")
    parser.add_argument(
        "--record", required=True, help="JSONL output path (overwrites)"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=DEFAULT_HZ,
        help=f"sample rate Hz (default: {DEFAULT_HZ})",
    )
    args = parser.parse_args()

    try:
        from scservo_sdk import (  # type: ignore[import-untyped]
            GroupSyncRead,
            PacketHandler,
            PortHandler,
        )
    except ImportError:
        sys.stderr.write(
            "ERROR: scservo_sdk not installed.\n"
            "       Install the [teaching] extra: uv sync --extra teaching\n"
        )
        return 1

    arm = PortHandler(args.arm)
    if not arm.openPort():
        sys.stderr.write(f"ERROR: cannot open arm port {args.arm}\n")
        return 1
    arm.setBaudRate(BAUD)
    packet = PacketHandler(0)
    set_torque(packet, arm, 0)
    reader = GroupSyncRead(arm, packet, ADDR_PRESENT_POSITION, 2)
    for sid in SERVO_IDS:
        reader.addParam(sid)

    print(
        f"[record] sampling arm at {args.rate:.1f} Hz "
        "(torque off — move the arm by hand)"
    )
    print(f"[record] writing JSONL to {args.record} (Ctrl-C to stop)")
    ticks = 0
    with open(args.record, "w") as record_file:
        try:
            for n in _record_loop(reader, packet, arm, record_file, args.rate):
                ticks = n
        except KeyboardInterrupt:
            print(f"\n[record] stopped after {ticks} ticks")
    # Torque stays off on exit so the operator can keep manipulating; replay
    # script re-enables it at startup when needed.
    arm.closePort()
    return 0


if __name__ == "__main__":
    sys.exit(main())
