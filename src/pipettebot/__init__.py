"""pipettebot — i3 Mega gantry + dPette pipette composition layer."""

from pipettebot.bot import PipetteBot
from pipettebot.cli_profile import build_volumes, resolve_profile
from pipettebot.gantry import GcodeGantry
from pipettebot.profiles import ExperimentProfile, load_profile

__all__ = [
    "ExperimentProfile",
    "GcodeGantry",
    "PipetteBot",
    "build_volumes",
    "load_profile",
    "resolve_profile",
]
__version__ = "0.0.1"
