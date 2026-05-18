"""Capture follower joint vector as a yaml-paste line for configs/so101_arms.yaml.

Composition-only wrapper over `so101.DualArmController` (no subclassing, no
override). Imported only when the `[orchestrator]` extra is installed; the
console script `pipettebot-capture-position` is the user-facing entry point.

Workflow:
    Terminal A (in so101-biolab-automation/):  make start_teleop
    Terminal B (in this repo, per waypoint):
        uv run pipettebot-capture-position --name=demo_pickup_approach

    The printed line goes under `positions:` in `configs/so101_arms.yaml` —
    overwrite the matching placeholder.

Under SO101_STUB_MODE=1 (no lerobot / no hardware) the joint vector is whatever
was last sent via `send_action` on the same controller instance; with no prior
action the vector is empty and the printed line reads `  <name>: []`.
"""

from __future__ import annotations

import argparse

from so101.arms import DualArmConfig, DualArmController


def _format_joints_as_yaml_line(name: str, joints: list[float]) -> str:
    """Format a joint vector as a yaml-paste line for the `positions:` mapping."""
    formatted = ", ".join(f"{j:.4f}" for j in joints)
    return f"  {name}: [{formatted}]"


def capture(config_path: str, arm: str, name: str) -> str:
    """Read the follower's current joint vector and return a yaml-paste line."""
    config = DualArmConfig.from_yaml(config_path)
    controller = DualArmController(config)
    controller.connect()
    try:
        joints = controller.get_observation(arm)["joints"]
    finally:
        controller.disconnect()
    return _format_joints_as_yaml_line(name, joints)


def main() -> None:
    """CLI entry point for capturing a follower's joint vector."""
    parser = argparse.ArgumentParser(
        description="Print follower joint vector as a yaml-paste line.",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="position name (e.g. demo_pickup_approach)",
    )
    parser.add_argument(
        "--arm",
        default="arm_a",
        help="arm id (default: arm_a)",
    )
    parser.add_argument(
        "--config",
        default="configs/so101_arms.yaml",
        help="config path (default: configs/so101_arms.yaml)",
    )
    args = parser.parse_args()
    print(capture(args.config, args.arm, args.name))


if __name__ == "__main__":
    main()
