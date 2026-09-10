"""Tests for `pipettebot.orchestrator` — composition over so101.DualArmController.

`validate_sequence_positions` and `run_sequence` are pure duck-typed functions
against the `_ArmController` Protocol (see orchestrator.py) — they're exercised
here with local fakes and need no so101 install. Only `TestLoadSo101Controller`
and `TestProjectConfigHasDemoKeys` touch the real so101 package (via
`load_so101_controller` / `DualArmConfig.from_yaml`) and are individually
skipped when the optional `[orchestrator]` extra (so101) isn't installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pipettebot.so101.orchestrator import (
    DEMO_PICKUP_SEQUENCE,
    load_so101_controller,
    run_sequence,
    validate_sequence_positions,
)


@pytest.fixture(autouse=True)
def _stub_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SO101_STUB_MODE", "1")


@dataclass
class _FakeArmConfig:
    """Structurally satisfies `_ArmController.config` (`.positions` only)."""

    positions: dict[str, list[float]]


@dataclass
class _FakeArmController:
    """Structurally satisfies the `_ArmController` Protocol — no so101 needed."""

    config: _FakeArmConfig
    fail_execute: bool = False
    executed: list[tuple[str, list[str]]] = field(default_factory=list)
    parked: bool = False
    connected: bool = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def execute_sequence(self, arm_id: str, position_names: list[str]) -> None:
        if self.fail_execute:
            raise RuntimeError("sequence failed")
        self.executed.append((arm_id, position_names))

    def park_all(self) -> None:
        self.parked = True

    def get_observation(self, arm_id: str) -> dict[str, object]:
        return {"joints": [0.0] * 6}


def _make_config(*, with_demo_keys: bool = True) -> _FakeArmConfig:
    positions: dict[str, list[float]] = {"park": [0.0] * 6}
    if with_demo_keys:
        for i, name in enumerate(DEMO_PICKUP_SEQUENCE):
            positions[name] = [float(i), 0.0, 0.0, 0.0, 0.0, 0.0]
    return _FakeArmConfig(positions=positions)


class TestValidateSequencePositions:
    def test_passes_when_all_present(self) -> None:
        cfg = _make_config(with_demo_keys=True)
        validate_sequence_positions(cfg, DEMO_PICKUP_SEQUENCE)

    def test_raises_key_error_on_first_missing(self) -> None:
        cfg = _make_config(with_demo_keys=False)
        with pytest.raises(KeyError, match=DEMO_PICKUP_SEQUENCE[0]):
            validate_sequence_positions(cfg, DEMO_PICKUP_SEQUENCE)


class TestRunSequence:
    def test_calls_full_sequence_in_order(self) -> None:
        ctrl = _FakeArmController(config=_make_config(with_demo_keys=True))
        run_sequence(ctrl, "arm_a", DEMO_PICKUP_SEQUENCE)
        assert ctrl.executed == [("arm_a", list(DEMO_PICKUP_SEQUENCE))]

    def test_parks_on_failure(self) -> None:
        ctrl = _FakeArmController(
            config=_make_config(with_demo_keys=True), fail_execute=True
        )
        with pytest.raises(RuntimeError, match="sequence failed"):
            run_sequence(ctrl, "arm_a", DEMO_PICKUP_SEQUENCE)
        assert ctrl.parked is True


class TestLoadSo101Controller:
    def test_loads_and_connects_under_stub(self) -> None:
        pytest.importorskip("so101")
        ctrl = load_so101_controller("configs/so101_arms.yaml")
        assert ctrl.is_connected
        ctrl.disconnect()


class TestProjectConfigHasDemoKeys:
    def test_demo_pickup_keys_present_in_repo_config(self) -> None:
        pytest.importorskip("so101")
        from so101.arms import DualArmConfig

        cfg = DualArmConfig.from_yaml("configs/so101_arms.yaml")
        for name in DEMO_PICKUP_SEQUENCE:
            assert name in cfg.positions, f"missing {name!r} in configs/so101_arms.yaml"
