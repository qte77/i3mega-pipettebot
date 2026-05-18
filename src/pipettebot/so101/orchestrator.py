"""SO-101 orchestrator — composition over `so101.DualArmController`.

The rows showcase calls `run_sequence(...)` after the i3 finishes its final
`G28 + M400`. The controller is loaded via `load_so101_controller()` and the
sequence is preflighted with `validate_sequence_positions()` BEFORE any i3
motion so a missing yaml key fails fast.

Only `so101.DualArmController`'s public API is touched — no subclassing,
monkey-patching, or vendoring. Failure path parks the arm before propagating
to prevent leaving the gripper in deck space.

Imported lazily by callers (showcase reads `SO101_CONFIG` env first); the
`[orchestrator]` extra installs the so101 dep.
"""

from __future__ import annotations

from so101.arms import DualArmConfig, DualArmController

DEMO_PICKUP_SEQUENCE: tuple[str, ...] = (
    "demo_pickup_approach",
    "demo_pickup_grip",
    "demo_pickup_lift",
    "demo_pickup_rotate",
)


def load_so101_controller(config_path: str) -> DualArmController:
    """Load the so101 arms config and return a connected controller."""
    config = DualArmConfig.from_yaml(config_path)
    controller = DualArmController(config)
    controller.connect()
    return controller


def validate_sequence_positions(
    config: DualArmConfig,
    sequence: tuple[str, ...],
) -> None:
    """Assert every name in `sequence` is defined in `config.positions`.

    Raises `KeyError` on the first missing name. Call BEFORE any motion so a
    yaml drift fails fast instead of mid-run.
    """
    for name in sequence:
        if name not in config.positions:
            raise KeyError(name)


def run_sequence(
    controller: DualArmController,
    arm_id: str,
    sequence: tuple[str, ...],
) -> None:
    """Execute the named-position sequence; park the arm if anything fails."""
    try:
        controller.execute_sequence(arm_id, list(sequence))
    except Exception:
        controller.park_all()
        raise
