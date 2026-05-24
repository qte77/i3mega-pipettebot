"""Shared STS3215 protocol + motion-profile + JSONL helpers for lean teleop tools.

Used by `tools/teleop_lean.py` (record) and `tools/teleop_replay.py` (playback).
Underscore prefix marks this as internal to the tools/ directory — not a
supported library API.

No scservo_sdk import: every function takes a duck-typed packet/port/writer
so unit tests can substitute fakes without touching hardware.
"""

from __future__ import annotations

import json
import os

# STS3215 control table (Feetech STS series)
ADDR_TORQUE_ENABLE = 0x28
ADDR_ACC = 0x29
ADDR_GOAL_POSITION = 0x2A
ADDR_GOAL_TIME = 0x2C
ADDR_GOAL_VELOCITY = 0x2E
ADDR_PRESENT_POSITION = 0x38

SERVO_IDS = (1, 2, 3, 4, 5, 6)
BAUD = 1_000_000


def env_int(name: str, default: int) -> int:
    """Return int from env var `name`, falling back to `default` if unset/empty."""
    raw = os.environ.get(name, "")
    return int(raw) if raw else default


# Follower motion-profile defaults — clamp slew rate so missed sample windows
# don't manifest as a violent step on the receiver. ACC is 1 byte (0-254);
# Goal_Velocity is ticks/sec (0 = uncapped). Override per-invocation via env
# vars without editing the file.
FOLLOWER_ACC = env_int("FOLLOWER_ACC", 40)
FOLLOWER_VEL_CAP = env_int("FOLLOWER_VEL_CAP", 2000)


def set_torque(packet: object, port: object, enabled: int) -> None:
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


def clamp_position(pos: int) -> int:
    """Clamp a raw STS3215 read to the valid 12-bit position range [0, 4095].

    Mixed-firmware setups (STS3215 firmware 3.9 + 3.10) can return corrupted
    sync_read responses where individual joint reads come back as huge
    positives (sign-extended negatives) — e.g., 32833 observed in
    session_001.jsonl. Writing those raw bytes as Goal_Position drives the
    servo to a nonsense position (low byte taken, high byte ignored). Mirrors
    the clamp in so101-patch-lerobot's `calibration_clamp` patch.
    """
    return max(0, min(4095, pos))


def write_follower_goals(writer: object, goals: dict[int, int]) -> None:
    """Sync-write Goal_Position to each servo in `goals` (no-op if empty)."""
    if not goals:
        return
    writer.clearParam()  # type: ignore[attr-defined]
    for sid, pos in goals.items():
        writer.addParam(sid, [pos & 0xFF, (pos >> 8) & 0xFF])  # type: ignore[attr-defined]
    writer.txPacket()  # type: ignore[attr-defined]


def format_record_line(t: float, joints: dict[int, int]) -> str:
    """Format one tick as a JSONL line: '{"t": <secs>, "joints": {sid: pos}}\\n'.

    Time is rounded to 1ms — sufficient for 60 Hz cadence, keeps lines short.
    Joint IDs serialize as JSON string keys (a JSON object constraint);
    `parse_record_line` coerces them back to int.
    """
    record = {"t": round(t, 3), "joints": joints}
    return json.dumps(record) + "\n"


def parse_record_line(line: str) -> tuple[float, dict[int, int]]:
    """Parse one JSONL recording line into (t_secs, {sid: pos}).

    Inverse of `format_record_line`. Coerces JSON string keys back to int
    servo ids so the result can be passed directly to `write_follower_goals`.
    """
    record = json.loads(line)
    return float(record["t"]), {int(k): int(v) for k, v in record["joints"].items()}
