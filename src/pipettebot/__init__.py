"""pipettebot — i3 Mega gantry + dPette pipette composition layer."""

from pipettebot.bot import PipetteBot
from pipettebot.cli_profile import build_volumes, resolve_profile
from pipettebot.devices import (
    FIRMWARE_POLICIES,
    DiscoveredDevice,
    FirmwarePolicy,
    classify,
    discover,
    parse_m115,
    policy_for,
    resolve_port,
)
from pipettebot.experiment_profile import ExperimentProfile, load_experiment_profile
from pipettebot.gantry import GcodeGantry, send_and_wait_for_ok
from pipettebot.motion_profile import MotionProfile, select_profile

__all__ = [
    "FIRMWARE_POLICIES",
    "DiscoveredDevice",
    "ExperimentProfile",
    "FirmwarePolicy",
    "GcodeGantry",
    "MotionProfile",
    "PipetteBot",
    "build_volumes",
    "classify",
    "discover",
    "load_experiment_profile",
    "parse_m115",
    "policy_for",
    "resolve_port",
    "resolve_profile",
    "select_profile",
    "send_and_wait_for_ok",
]
__version__ = "0.1.0"
