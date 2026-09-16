"""PipetteBot — composes a Marlin gantry with a dPette pipette."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pipettebot.gantry import GcodeGantry

# dPette+ 8-channel: channel spacing matches SBS row pitch (see docs/3d-parts.md
# "SBS labware reference"). The 8 channels share one physical piston bar, so a
# single aspirate/dispense call always applies the same volume to all 8 — there
# is no independent per-channel addressing. This constant exists for callers
# computing well-column XY offsets by hand; it is not consumed by PipetteBot
# itself (deck/well geometry is deferred, see AGENT_REQUESTS.md and issue #10).
COLUMN_PITCH_MM = 9.0


class _Pipette(Protocol):
    """Subset of dpette.DPetteDriver used by PipetteBot (lets tests inject fakes)."""

    def aspirate(self, volume_ul: float = ...) -> object: ...
    def dispense(self, volume_ul: float = ...) -> object: ...


class PipetteBot:
    """Move-then-pipette composer.

    Caller owns coordinate frames. v0 takes raw (x, y, z) — deck geometry,
    well-plate frames, and tip handling are deferred (see AGENT_REQUESTS.md).
    """

    def __init__(self, gantry: GcodeGantry, pipette: _Pipette) -> None:
        """Compose `gantry` and `pipette` into a single move-then-pipette unit."""
        self._gantry = gantry
        self._pipette = pipette

    def aspirate_at(self, x: float, y: float, z: float, volume_ul: float) -> None:
        """Move to `(x, y, z)`, wait for the move, then aspirate `volume_ul`."""
        self._gantry.move_to(x, y, z)
        self._gantry.wait_for_moves()
        self._pipette.aspirate(volume_ul)

    def dispense_at(self, x: float, y: float, z: float) -> None:
        """Move to `(x, y, z)`, wait for the move, then dispense."""
        self._gantry.move_to(x, y, z)
        self._gantry.wait_for_moves()
        self._pipette.dispense()

    def home(self) -> None:
        """Home all gantry axes and wait for the move to complete."""
        self._gantry.home()
        self._gantry.wait_for_moves()
