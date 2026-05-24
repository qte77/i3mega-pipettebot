"""Unit tests for tools/teleop_postprocess.py — smoothing + speed scaling."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _import_teleop_postprocess():
    spec = importlib.util.spec_from_file_location(
        "teleop_postprocess", TOOLS_DIR / "teleop_postprocess.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["teleop_postprocess"] = mod
    spec.loader.exec_module(mod)
    return mod


teleop_postprocess = _import_teleop_postprocess()


def test_smooth_window_size_1_is_identity() -> None:
    assert teleop_postprocess.smooth_window([10, 20, 30], window=1) == [10, 20, 30]


def test_smooth_window_returns_same_length_as_input() -> None:
    out = teleop_postprocess.smooth_window([1, 2, 3, 4, 5], window=3)
    assert len(out) == 5


def test_smooth_window_averages_three_centered() -> None:
    # window=3, centered. Edges average over the truncated window only.
    assert teleop_postprocess.smooth_window([10, 20, 30, 40, 50], window=3) == [
        15,
        20,
        30,
        40,
        45,
    ]


def test_smooth_window_averages_five_centered() -> None:
    assert teleop_postprocess.smooth_window([10, 20, 30, 40, 50], window=5) == [
        20,
        25,
        30,
        35,
        40,
    ]


def test_smooth_window_clamps_negative_and_overflow() -> None:
    out = teleop_postprocess.smooth_window([-100, 0, 4095, 5000], window=1)
    assert out == [0, 0, 4095, 4095]


def test_smooth_window_handles_empty_list() -> None:
    assert teleop_postprocess.smooth_window([], window=5) == []


def test_postprocess_scales_timestamps_by_speed_factor() -> None:
    records = [(0.0, {1: 100}), (1.0, {1: 200}), (2.0, {1: 300})]
    out = teleop_postprocess.postprocess(records, smooth=1, speed=2.0)
    assert [t for t, _ in out] == [0.0, 0.5, 1.0]


def test_postprocess_smooths_joints_per_servo_independently() -> None:
    records = [
        (0.0, {1: 100, 2: 200}),
        (1.0, {1: 200, 2: 300}),
        (2.0, {1: 300, 2: 400}),
    ]
    out = teleop_postprocess.postprocess(records, smooth=3, speed=1.0)
    assert [j for _, j in out] == [
        {1: 150, 2: 250},
        {1: 200, 2: 300},
        {1: 250, 2: 350},
    ]


def test_postprocess_preserves_int_servo_ids() -> None:
    records = [(0.0, {1: 100})]
    out = teleop_postprocess.postprocess(records, smooth=1, speed=1.0)
    assert all(isinstance(k, int) for _, joints in out for k in joints)


def test_postprocess_returns_empty_on_empty_input() -> None:
    assert teleop_postprocess.postprocess([], smooth=5, speed=2.0) == []


def test_postprocess_rounds_timestamps_to_milliseconds() -> None:
    records = [(0.123456, {1: 100})]
    out = teleop_postprocess.postprocess(records, smooth=1, speed=1.0)
    assert out[0][0] == 0.123
