"""Smooth + speed-scale a teleop_lean / teleop_record JSONL recording.

Reads a JSONL recording, applies a centered moving-average smoother per
servo column, scales timestamps by a constant factor, and writes a new
JSONL file. Use to clean encoder jitter and / or compress the wall-clock
duration before replay.

Usage:
    uv run --extra teaching python tools/teleop_postprocess.py \\
        --in=captures/session_010.jsonl \\
        --out=captures/session_010_smoothed_2.5x.jsonl \\
        --smooth=35 --speed=2.5

Defaults: smooth=1 (identity, no smoothing), speed=1.0 (identity, no
scaling) — explicit override required for any change. Output positions
are clamped to the 12-bit STS3215 range [0, 4095] regardless of input.

Caveats:

- Smoothing window N introduces N//2 ticks (~N//2 * 17ms at 60 Hz) of
  lag in transitions. Sharp keyframes blur into ramps.
- Speed scaling > 1 multiplies peak per-servo velocity by the same
  factor; if the original recording had peaks near the STS3215 ceiling
  (~5000-6000 ticks/s), a 2x speedup will exceed it and the follower
  will fall behind on replay.

Pure-Python, no scservo_sdk — runs anywhere, including headless CI.
"""

from __future__ import annotations

import argparse
import sys

from _teleop_common import (
    clamp_position,
    format_record_line,
    parse_record_line,
)


def smooth_window(values: list[int], window: int) -> list[int]:
    """Centered moving-average over `values`; clamped to [0, 4095] and int.

    `window=1` is the identity. At each index `i` the average covers the
    half-open slice `[i - window//2, i + window//2 + 1)` clipped to the
    list bounds, so edges average over a truncated window only (no zero
    padding, no reflection — keeps the endpoints faithful to the input).
    """
    if not values:
        return []
    half = window // 2
    n = len(values)
    out: list[int] = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        avg = sum(values[lo:hi]) / (hi - lo)
        out.append(clamp_position(round(avg)))
    return out


def postprocess(
    records: list[tuple[float, dict[int, int]]],
    *,
    smooth: int,
    speed: float,
) -> list[tuple[float, dict[int, int]]]:
    """Apply per-servo smoothing and timestamp scaling to a tick stream.

    Each record is `(t_seconds, {sid: ticks})`. Output preserves int
    servo IDs and rounds timestamps to 1 ms precision (matching what
    `format_record_line` emits).
    """
    if not records:
        return []
    sids = sorted({sid for _, joints in records for sid in joints})
    per_sid = {sid: [joints.get(sid, 2048) for _, joints in records] for sid in sids}
    smoothed = {sid: smooth_window(vals, smooth) for sid, vals in per_sid.items()}
    return [
        (round(t / speed, 3), {sid: smoothed[sid][i] for sid in sids})
        for i, (t, _) in enumerate(records)
    ]


def _read_records(path: str) -> list[tuple[float, dict[int, int]]]:
    """Read a JSONL recording into a list of (t, joints) tuples."""
    with open(path) as f:
        return [parse_record_line(line) for line in f if line.strip()]


def _write_records(path: str, records: list[tuple[float, dict[int, int]]]) -> None:
    """Write a JSONL recording from a list of (t, joints) tuples."""
    with open(path, "w") as f:
        for t, joints in records:
            f.write(format_record_line(t, joints))


def main() -> int:
    """CLI entry: read, transform, write, report."""
    parser = argparse.ArgumentParser(
        description=("Smooth + speed-scale a teleop JSONL recording (no scservo_sdk)."),
    )
    parser.add_argument("--in", dest="in_path", required=True, help="input JSONL")
    parser.add_argument(
        "--out", dest="out_path", required=True, help="output JSONL (overwrites)"
    )
    parser.add_argument(
        "--smooth",
        type=int,
        default=1,
        help="centered moving-average window in ticks (default: 1 = no smoothing)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="timestamp divisor; 2.0 plays in half the time (default: 1.0)",
    )
    args = parser.parse_args()
    if args.smooth < 1:
        sys.stderr.write("ERROR: --smooth must be >= 1\n")
        return 1
    if args.speed <= 0:
        sys.stderr.write("ERROR: --speed must be > 0\n")
        return 1

    records = _read_records(args.in_path)
    if not records:
        sys.stderr.write(f"ERROR: no records in {args.in_path}\n")
        return 1
    transformed = postprocess(records, smooth=args.smooth, speed=args.speed)
    _write_records(args.out_path, transformed)

    in_duration = records[-1][0]
    out_duration = transformed[-1][0]
    print(f"[postprocess] wrote {len(transformed)} ticks to {args.out_path}")
    print(f"  smoothing window: {args.smooth} ticks (~{args.smooth * 17}ms at 60 Hz)")
    print(
        f"  speed factor:     {args.speed}x  "
        f"(in: {in_duration:.2f}s, out: {out_duration:.2f}s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
