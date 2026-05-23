"""pipettebot — i3 Mega gantry + dPette pipette composition layer."""

from pipettebot.bot import PipetteBot
from pipettebot.cli_profile import build_volumes, resolve_profile
from pipettebot.experiment_profile import ExperimentProfile, load_experiment_profile
from pipettebot.gantry import GcodeGantry
from pipettebot.motion_profile import MotionProfile, select_profile

__all__ = [
    "ExperimentProfile",
    "GcodeGantry",
    "MotionProfile",
    "PipetteBot",
    "build_volumes",
    "load_experiment_profile",
    "resolve_profile",
    "select_profile",
]
__version__ = "0.1.0"
