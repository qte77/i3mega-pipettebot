"""PipetteBot — composes a Marlin gantry with a dPette pipette."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pipettebot.gantry import GcodeGantry


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
        self._gantry = gantry
        self._pipette = pipette

    def aspirate_at(self, x: float, y: float, z: float, volume_ul: float) -> None:
        self._gantry.move_to(x, y, z)
        self._gantry.wait_for_moves()
        self._pipette.aspirate(volume_ul)

    def dispense_at(self, x: float, y: float, z: float) -> None:
        self._gantry.move_to(x, y, z)
        self._gantry.wait_for_moves()
        self._pipette.dispense()

    def home(self) -> None:
        self._gantry.home()
        self._gantry.wait_for_moves()
