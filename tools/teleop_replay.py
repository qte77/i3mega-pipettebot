"""Lean follower replay — drive the SO-101 follower from a recorded session.

Reads a JSONL recording produced by `tools/teleop_lean.py --record=...` and
sync-writes Goal_Position to the follower at the original cadence. No leader,
no lerobot, no torch.

Open-loop: the follower's PID tracks each goal but won't recover from
workspace drift or any change since the recording. Re-record if the
environment changes.

Usage:
    uv run --extra teaching python tools/teleop_replay.py \\
        --follower=/dev/ttyACM1 \\
        --record=captures/session_002.jsonl

Same follower-side motion profile as teleop_lean.py — env vars
`FOLLOWER_ACC` and `FOLLOWER_VEL_CAP` override defaults.

Press Ctrl-C to abort; follower torque is disabled on exit.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import TYPE_CHECKING

from _teleop_common import (
    ADDR_GOAL_POSITION,
    BAUD,
    FOLLOWER_ACC,
    FOLLOWER_VEL_CAP,
    SERVO_IDS,
    parse_record_line,
    set_torque,
    setup_follower_motion,
    write_follower_goals,
)

if TYPE_CHECKING:
    from typing import IO


def _replay_loop(writer: object, record_file: IO[str]):  # type: ignore[no-untyped-def]
    """Iterate JSONL ticks; sync-write goals at the original cadence.

    Yields the 1-based tick index after each successful write so callers
    can track progress under SIGINT. `time.sleep` schedules the next
    write to land at its recorded `t` relative to the first tick we
    processed — drift accumulates if the host can't keep up but each
    individual write is anchored to the recording's wall-clock.
    """
    t0 = time.perf_counter()
    idx = 0
    for raw_line in record_file:
        line = raw_line.strip()
        if not line:
            continue
        t_record, goals = parse_record_line(line)
        elapsed = time.perf_counter() - t0
        if t_record > elapsed:
            time.sleep(t_record - elapsed)
        write_follower_goals(writer, goals)
        idx += 1
        yield idx


def main() -> int:
    """Replay a teleop_lean JSONL recording onto the follower."""
    parser = argparse.ArgumentParser(
        description=(
            "Replay a recorded SO-101 trajectory onto the follower "
            "(open-loop, no lerobot)."
        ),
    )
    parser.add_argument("--follower", required=True, help="follower serial port path")
    parser.add_argument(
        "--record",
        required=True,
        help="JSONL recording path (from `teleop_lean.py --record`)",
    )
    args = parser.parse_args()

    try:
        from scservo_sdk import (  # type: ignore[import-untyped]
            GroupSyncWrite,
            PacketHandler,
            PortHandler,
        )
    except ImportError:
        sys.stderr.write(
            "ERROR: scservo_sdk not installed.\n"
            "       Install the [teaching] extra: uv sync --extra teaching\n"
        )
        return 1

    follower = PortHandler(args.follower)
    if not follower.openPort():
        sys.stderr.write(f"ERROR: cannot open follower port {args.follower}\n")
        return 1
    follower.setBaudRate(BAUD)
    packet = PacketHandler(0)

    set_torque(packet, follower, 1)
    setup_follower_motion(packet, follower, acc=FOLLOWER_ACC, vel_cap=FOLLOWER_VEL_CAP)
    writer = GroupSyncWrite(follower, packet, ADDR_GOAL_POSITION, 2)
    # SERVO_IDS is implicit in write_follower_goals; we don't pre-register here
    # because each tick may carry a subset of servos.
    _ = SERVO_IDS  # silence unused-import; constant is part of the contract

    print(
        f"[replay] follower motion-profile: "
        f"ACC={FOLLOWER_ACC} VEL_CAP={FOLLOWER_VEL_CAP} (Goal_Time forced to 0)"
    )
    print(f"[replay] streaming {args.record} -> follower (Ctrl-C to abort)")
    ticks = 0
    try:
        with open(args.record) as f:
            for n in _replay_loop(writer, f):
                ticks = n
        print(f"[replay] done ({ticks} ticks)")
    except KeyboardInterrupt:
        print(f"\n[replay] aborted after {ticks} ticks; disabling torque...")
    finally:
        set_torque(packet, follower, 0)
        follower.closePort()
    return 0


if __name__ == "__main__":
    sys.exit(main())
