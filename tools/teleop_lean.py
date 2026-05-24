"""Minimal leader -> follower SO-101 teleop via scservo-sdk.

No lerobot, no torch. Mirrors the 6 STS3215 servo positions from the
leader arm onto the follower at ~30 Hz. Use this for the demo_pickup_*
teaching workflow when the lerobot stack is overkill (or torch is
unwelcome).

Filed upstream as qte77/so101-biolab-automation#160 (eventual home is
either so101's lean-runtime split #158 or a dedicated lean CLI there).

Usage:
    uv sync --extra teaching                     # one-time
    uv run --extra teaching \\
        python tools/teleop_lean.py \\
        --leader=/dev/ttyACM0 \\
        --follower=/dev/ttyACM1

Ports come from `lerobot-find-port` (in so101 repo) or any tool that
reports the CH340/CP2102 paths for your leader + follower.

Press Ctrl-C to stop; follower torque is disabled on exit so the arm
can be moved freely by hand.

Tune smoothing live without editing the file via env vars (defaults shown):

    FOLLOWER_ACC=40 FOLLOWER_VEL_CAP=2000 uv run --extra teaching \\
        python tools/teleop_lean.py --leader=... --follower=... --rate=60

Capture the follower's current joints (lean — raw STS3215 ticks) by
sending SIGUSR1 to the script from another terminal:

    kill -USR1 $(pgrep -f teleop_lean)

The PID is printed at startup. Each capture prints one yaml-ish line
to stdout — convert from raw ticks to the calibrated frame before
pasting into configs/so101_arms.yaml.

Record the leader joint stream for later open-loop replay:

    uv run --extra teaching python tools/teleop_lean.py \\
        --leader=... --follower=... --record=captures/session.jsonl

JSONL format: one `{"t": secs_since_start, "joints": {sid: pos, ...}}`
line per tick. Replay via `tools/teleop_replay.py` (when added).

STS3215 control table addresses are from the Feetech STS series manual.
SO-101 has 6 servos addressed 1..6.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import IO

# STS3215 control table (Feetech STS series)
ADDR_TORQUE_ENABLE = 0x28
ADDR_ACC = 0x29
ADDR_GOAL_POSITION = 0x2A
ADDR_GOAL_TIME = 0x2C
ADDR_GOAL_VELOCITY = 0x2E
ADDR_PRESENT_POSITION = 0x38

SERVO_IDS = (1, 2, 3, 4, 5, 6)
BAUD = 1_000_000
DEFAULT_HZ = 30.0


# Follower motion-profile defaults — clamp slew rate so missed sample windows
# don't manifest as a violent step on the receiver. ACC is 1 byte (0-254);
# Goal_Velocity is ticks/sec (0 = uncapped). Tuned on STS3215 @ 1 Mbaud; tune
# down for smoother motion, up for snappier response. Override via env vars
# without editing the file: `FOLLOWER_ACC=80 FOLLOWER_VEL_CAP=5000 uv run ...`.
def _env_int(name: str, default: int) -> int:
    """Return int from env var `name`, falling back to `default` if unset/empty."""
    raw = os.environ.get(name, "")
    return int(raw) if raw else default


FOLLOWER_ACC = _env_int("FOLLOWER_ACC", 40)
FOLLOWER_VEL_CAP = _env_int("FOLLOWER_VEL_CAP", 2000)


def _set_torque(packet: object, port: object, enabled: int) -> None:
    """Write `enabled` (0 or 1) to ADDR_TORQUE_ENABLE for every SERVO_IDS entry."""
    for sid in SERVO_IDS:
        packet.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, enabled)  # type: ignore[attr-defined]


def setup_follower_motion(
    packet: object, port: object, *, acc: int, vel_cap: int
) -> None:
    """Configure follower-side ACC, Goal_Velocity, Goal_Time for live mirroring.

    Writes once at startup. Three registers, each addressing a separate
    failure mode:

    - `ACC` and `Goal_Velocity` cap the slew rate so a stale `Goal_Position`
      jump doesn't slew at default max acceleration (violent jerk).
    - `Goal_Time` is forced to 0 — when non-zero (lerobot-calibrate leaves
      it set on some firmwares), STS3215 treats each `Goal_Position` as
      "reach this in N ms" and ignores `Goal_Velocity` entirely. The
      observable symptom is the follower only catching up after every
      second leader move while individual moves complete a time-budgeted
      slope.
    """
    for sid in SERVO_IDS:
        packet.write1ByteTxRx(port, sid, ADDR_ACC, acc)  # type: ignore[attr-defined]
        packet.write2ByteTxRx(port, sid, ADDR_GOAL_TIME, 0)  # type: ignore[attr-defined]
        packet.write2ByteTxRx(port, sid, ADDR_GOAL_VELOCITY, vel_cap)  # type: ignore[attr-defined]


def format_capture_line(name: str, joint_ticks: list[int]) -> str:
    """Format a raw STS3215 joint vector as a yaml-paste line.

    Lean teleop has no calibrated-frame conversion (that lives in the so101
    full stack). The emitted line carries raw 0-4095 ticks with an inline
    comment so it can't be mistaken for the calibrated yaml the orchestrator
    expects. Convert before pasting into configs/so101_arms.yaml.
    """
    formatted = ", ".join(str(j) for j in joint_ticks)
    return f"  {name}: [{formatted}]  # raw STS3215 ticks"


def read_follower_positions(reader: object) -> dict[int, int] | None:
    """Sync-read follower joint positions; return None on bus failure or no data.

    Used by the SIGUSR1 capture path. Mirrors `_mirror_tick`'s read half but
    returns the dict (or None) instead of forwarding to a writer.
    """
    if reader.txRxPacket() != 0:  # type: ignore[attr-defined]
        return None
    positions: dict[int, int] = {}
    for sid in SERVO_IDS:
        if reader.isAvailable(sid, ADDR_PRESENT_POSITION, 2):  # type: ignore[attr-defined]
            positions[sid] = reader.getData(sid, ADDR_PRESENT_POSITION, 2)  # type: ignore[attr-defined]
    return positions or None


@dataclass
class _CaptureState:
    """SIGUSR1-driven capture flag + counter, mutated by the signal handler."""

    requested: bool = False
    counter: int = 0


def consume_capture(state: _CaptureState, reader: object) -> str | None:
    """Drain a pending SIGUSR1 capture; return a yaml-paste line or None.

    Returns None when no capture is pending or the sync_read failed. The
    caller decides whether to print to stdout or stderr — keeps this
    function deterministic and testable.
    """
    if not state.requested:
        return None
    state.requested = False
    state.counter += 1
    positions = read_follower_positions(reader)
    if positions is None:
        return None
    joints = [positions.get(sid, 0) for sid in SERVO_IDS]
    return format_capture_line(f"captured_{state.counter}", joints)


def _run_loop(
    reader: object,
    writer: object,
    follower_reader: object,
    capture: _CaptureState,
    rate_hz: float,
    record_file: IO[str] | None = None,
) -> None:
    """Mirror leader -> follower forever; drain pending captures between ticks.

    When `record_file` is provided, each tick's leader goals are appended
    as a JSONL line with a session-relative timestamp (seconds since the
    first tick) for later open-loop replay via tools/teleop_replay.py.
    """
    period = 1.0 / rate_hz
    t0 = time.perf_counter()
    while True:
        tick = time.perf_counter()
        goals = _mirror_tick(reader, writer)
        if record_file is not None and goals:
            record_file.write(format_record_line(tick - t0, goals))
        line = consume_capture(capture, follower_reader)
        if line is not None:
            print(line)
        elapsed = time.perf_counter() - tick
        if elapsed < period:
            time.sleep(period - elapsed)


def _mirror_tick(reader: object, writer: object) -> dict[int, int]:
    """Sync-read all leader positions, sync-write available ones to follower.

    One bus exchange per direction instead of 12 sequential transactions —
    raises achievable update rate from ~15-20 Hz to 60+ Hz on the same wire.
    Transient per-servo read failures (isAvailable=False) are skipped; a
    full sync_read failure (non-zero txRxPacket) drops the entire tick.

    Returns the goals that were written this tick (empty dict if nothing
    was written), so the caller can log them for offline replay.
    """
    if reader.txRxPacket() != 0:  # type: ignore[attr-defined]
        return {}
    goals: dict[int, int] = {}
    for sid in SERVO_IDS:
        if reader.isAvailable(sid, ADDR_PRESENT_POSITION, 2):  # type: ignore[attr-defined]
            goals[sid] = reader.getData(sid, ADDR_PRESENT_POSITION, 2)  # type: ignore[attr-defined]
    if not goals:
        return {}
    writer.clearParam()  # type: ignore[attr-defined]
    for sid, pos in goals.items():
        writer.addParam(sid, [pos & 0xFF, (pos >> 8) & 0xFF])  # type: ignore[attr-defined]
    writer.txPacket()  # type: ignore[attr-defined]
    return goals


def format_record_line(t: float, joints: dict[int, int]) -> str:
    """Format one tick as a JSONL line: '{"t": <secs>, "joints": {sid: pos, ...}}\\n'.

    Time is rounded to 1ms — sufficient for 60 Hz cadence, keeps lines
    short. Joint IDs serialize as JSON string keys (a JSON object
    constraint); parsers must coerce them back to int.
    """
    record = {"t": round(t, 3), "joints": joints}
    return json.dumps(record) + "\n"


def main() -> int:
    """Mirror leader joint positions to the follower until Ctrl-C."""
    parser = argparse.ArgumentParser(
        description=(
            "Minimal leader -> follower SO-101 teleop (no lerobot, no torch)."
        ),
    )
    parser.add_argument("--leader", required=True, help="leader serial port path")
    parser.add_argument("--follower", required=True, help="follower serial port path")
    parser.add_argument(
        "--rate",
        type=float,
        default=DEFAULT_HZ,
        help=f"loop rate Hz (default: {DEFAULT_HZ})",
    )
    parser.add_argument(
        "--record",
        default=None,
        help=(
            "append leader joint stream as JSONL to this path (one line per tick)"
            " for later replay via tools/teleop_replay.py"
        ),
    )
    args = parser.parse_args()

    try:
        from scservo_sdk import (  # type: ignore[import-untyped]
            GroupSyncRead,
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

    leader = PortHandler(args.leader)
    follower = PortHandler(args.follower)
    if not leader.openPort():
        sys.stderr.write(f"ERROR: cannot open leader port {args.leader}\n")
        return 1
    if not follower.openPort():
        sys.stderr.write(f"ERROR: cannot open follower port {args.follower}\n")
        leader.closePort()
        return 1
    leader.setBaudRate(BAUD)
    follower.setBaudRate(BAUD)
    packet = PacketHandler(0)

    # Leader torque OFF (kinesthetic input — operator moves it by hand;
    # leftover torque from `lerobot-calibrate` causes servo fault / LED blink).
    # Follower torque ON so writes to goal_position actually move the arm.
    _set_torque(packet, leader, 0)
    _set_torque(packet, follower, 1)
    setup_follower_motion(packet, follower, acc=FOLLOWER_ACC, vel_cap=FOLLOWER_VEL_CAP)

    # GroupSyncRead/Write take (port, packet, addr, len) — port FIRST.
    reader = GroupSyncRead(leader, packet, ADDR_PRESENT_POSITION, 2)
    for sid in SERVO_IDS:
        reader.addParam(sid)
    writer = GroupSyncWrite(follower, packet, ADDR_GOAL_POSITION, 2)
    follower_reader = GroupSyncRead(follower, packet, ADDR_PRESENT_POSITION, 2)
    for sid in SERVO_IDS:
        follower_reader.addParam(sid)

    capture = _CaptureState()

    def _on_capture_signal(_signum: int, _frame: object) -> None:
        capture.requested = True

    signal.signal(signal.SIGUSR1, _on_capture_signal)

    print(f"[teleop] mirror leader -> follower @ {args.rate:.1f} Hz (Ctrl-C to stop)")
    print(
        f"[teleop] follower motion-profile: "
        f"ACC={FOLLOWER_ACC} VEL_CAP={FOLLOWER_VEL_CAP} (Goal_Time forced to 0)"
    )
    print(
        f"[teleop] capture follower joints: kill -USR1 {os.getpid()} "
        "(prints a yaml-paste line of raw ticks)"
    )
    record_file = open(args.record, "a") if args.record else None  # noqa: SIM115
    if record_file is not None:
        print(f"[teleop] recording leader joint stream to {args.record}")
    try:
        _run_loop(
            reader, writer, follower_reader, capture, args.rate, record_file=record_file
        )
    except KeyboardInterrupt:
        print("\n[teleop] stopping; disabling torque on both arms...")
    finally:
        if record_file is not None:
            record_file.close()
        _set_torque(packet, leader, 0)
        _set_torque(packet, follower, 0)
        leader.closePort()
        follower.closePort()
    return 0


if __name__ == "__main__":
    sys.exit(main())
