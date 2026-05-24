"""pipettebot — i3 Mega gantry + dPette pipette composition layer."""

from pipettebot.bot import PipetteBot
from pipettebot.cli_profile import build_volumes, resolve_profile
from pipettebot.devices import (
    FIRMWARE_POLICIES,
    PRINTER_PORT_ENV,
    DiscoveredDevice,
    FirmwarePolicy,
    classify,
    discover,
    parse_m115,
    policy_for,
    resolve_port,
    safe_home,
)
from pipettebot.experiment_profile import ExperimentProfile, load_experiment_profile
from pipettebot.gantry import (
    GcodeGantry,
    open_gcode_port,
    open_marlin_port,
    send_and_wait_for_ok,
)
from pipettebot.motion_profile import MotionProfile, select_profile

__all__ = [
    "FIRMWARE_POLICIES",
    "PRINTER_PORT_ENV",
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
    "open_gcode_port",
    "open_marlin_port",  # deprecated alias for open_gcode_port; removed in 0.2.x
    "parse_m115",
    "policy_for",
    "resolve_port",
    "resolve_profile",
    "safe_home",
    "select_profile",
    "send_and_wait_for_ok",
]
__version__ = "0.1.0"
