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

STS3215 control table addresses are from the Feetech STS series manual.
SO-101 has 6 servos addressed 1..6.
"""

from __future__ import annotations

import argparse
import sys
import time

# STS3215 control table (Feetech STS series)
ADDR_TORQUE_ENABLE = 0x28
ADDR_GOAL_POSITION = 0x2A
ADDR_PRESENT_POSITION = 0x38

SERVO_IDS = (1, 2, 3, 4, 5, 6)
BAUD = 1_000_000
DEFAULT_HZ = 30.0


def _set_torque(packet: object, port: object, enabled: int) -> None:
    """Write `enabled` (0 or 1) to ADDR_TORQUE_ENABLE for every SERVO_IDS entry."""
    for sid in SERVO_IDS:
        packet.write1ByteTxRx(port, sid, ADDR_TORQUE_ENABLE, enabled)  # type: ignore[attr-defined]


def _mirror_tick(packet: object, leader: object, follower: object) -> None:
    """One read-from-leader, write-to-follower pass over all six servos."""
    for sid in SERVO_IDS:
        pos, result, _ = packet.read2ByteTxRx(  # type: ignore[attr-defined]
            leader, sid, ADDR_PRESENT_POSITION
        )
        if result != 0:
            continue  # transient read failure; skip this servo this tick
        packet.write2ByteTxRx(follower, sid, ADDR_GOAL_POSITION, pos)  # type: ignore[attr-defined]


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
    args = parser.parse_args()

    try:
        from scservo_sdk import (  # type: ignore[import-untyped]
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

    period = 1.0 / args.rate
    print(f"[teleop] mirror leader -> follower @ {args.rate:.1f} Hz (Ctrl-C to stop)")
    try:
        while True:
            tick = time.perf_counter()
            _mirror_tick(packet, leader, follower)
            elapsed = time.perf_counter() - tick
            if elapsed < period:
                time.sleep(period - elapsed)
    except KeyboardInterrupt:
        print("\n[teleop] stopping; disabling torque on both arms...")
    finally:
        _set_torque(packet, leader, 0)
        _set_torque(packet, follower, 0)
        leader.closePort()
        follower.closePort()
    return 0


if __name__ == "__main__":
    sys.exit(main())
