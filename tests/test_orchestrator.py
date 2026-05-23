"""Tests for `pipettebot.orchestrator` — composition over so101.DualArmController.

Skipped entirely when the optional `[orchestrator]` extra (so101) isn't installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("so101")

from so101.arms import ArmConfig, DualArmConfig, DualArmController

from pipettebot.so101.orchestrator import (
    DEMO_PICKUP_SEQUENCE,
    load_so101_controller,
    run_sequence,
    validate_sequence_positions,
)


@pytest.fixture(autouse=True)
def _stub_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SO101_STUB_MODE", "1")


def _make_config(*, with_demo_keys: bool = True) -> DualArmConfig:
    positions: dict[str, list[float]] = {"park": [0.0] * 6}
    if with_demo_keys:
        for i, name in enumerate(DEMO_PICKUP_SEQUENCE):
            positions[name] = [float(i), 0.0, 0.0, 0.0, 0.0, 0.0]
    return DualArmConfig(
        arm_a=ArmConfig(arm_id="arm_a", port="/dev/null", role="follower"),
        arm_b=ArmConfig(arm_id="arm_b", port="/dev/null", role="follower"),
        positions=positions,
    )


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
        cfg = _make_config(with_demo_keys=True)
        ctrl = DualArmController(cfg)
        ctrl.connect()
        run_sequence(ctrl, "arm_a", DEMO_PICKUP_SEQUENCE)
        history = ctrl.get_observation("arm_a")["history"]
        assert len(history) == len(DEMO_PICKUP_SEQUENCE)
        for i, _ in enumerate(DEMO_PICKUP_SEQUENCE):
            assert history[i][0] == float(i)

    def test_parks_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = _make_config(with_demo_keys=True)
        ctrl = DualArmController(cfg)
        ctrl.connect()

        def fail(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("sequence failed")

        park_calls: list[bool] = []
        original_park = ctrl.park_all

        def tracked_park() -> None:
            park_calls.append(True)
            original_park()

        monkeypatch.setattr(ctrl, "execute_sequence", fail)
        monkeypatch.setattr(ctrl, "park_all", tracked_park)

        with pytest.raises(RuntimeError, match="sequence failed"):
            run_sequence(ctrl, "arm_a", DEMO_PICKUP_SEQUENCE)
        assert park_calls == [True]


class TestLoadSo101Controller:
    def test_loads_and_connects_under_stub(self) -> None:
        ctrl = load_so101_controller("configs/so101_arms.yaml")
        assert ctrl.is_connected
        ctrl.disconnect()


class TestProjectConfigHasDemoKeys:
    def test_demo_pickup_keys_present_in_repo_config(self) -> None:
        cfg = DualArmConfig.from_yaml("configs/so101_arms.yaml")
        for name in DEMO_PICKUP_SEQUENCE:
            assert name in cfg.positions, f"missing {name!r} in configs/so101_arms.yaml"
