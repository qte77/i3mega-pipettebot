"""Experiment profile loader for the v0 dPette showcases.

The dPette is an 8-channel pipette with a single shared piston bar, so
the smallest unit of volume control is "one volume per cycle, applied
to all 8 channels". A profile captures the per-cycle volume schedule
(plus optional reservoir gradient notes) in a TOML file that the
showcase scripts load via the `PIPETTE_PROFILE` env var.

Schema::

    name = "<short id>"             # optional; defaults to file stem
    description = "<freeform>"      # optional

    [volumes]
    # EITHER an explicit per-cycle list (length sets cycle count):
    per_cycle_ul = [v1, v2, ...]
    # OR a constant + cycle count:
    constant_ul = 100.0
    num_cycles = 11

    [gradient]
    description = "<operator-facing; never enforced by the script>"

See `examples/experiment_profiles/*.toml` for canonical examples.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


@dataclass(frozen=True)
class ExperimentProfile:
    """Parsed profile. `volumes_ul[i]` is the cycle-(i+1) volume in µL.

    `gradient_description` is operator-facing only — the dPette has no
    per-channel volume addressing, so cross-channel variation is encoded
    by pre-mixing the reservoir, not by the script.
    """

    name: str
    description: str
    volumes_ul: tuple[float, ...]
    gradient_description: str

    @property
    def num_cycles(self) -> int:
        """Number of cycles in the volume schedule."""
        return len(self.volumes_ul)


def _resolve_volumes(data: dict[str, Any], path: Path) -> tuple[float, ...]:
    volumes_block = data.get("volumes") or {}
    per_cycle = volumes_block.get("per_cycle_ul")
    constant = volumes_block.get("constant_ul")
    num_cycles = volumes_block.get("num_cycles")

    if per_cycle is not None and constant is not None:
        raise ValueError(
            f"{path}: set EITHER volumes.per_cycle_ul OR volumes.constant_ul, not both"
        )
    if per_cycle is None and constant is None:
        raise ValueError(
            f"{path}: must set one of volumes.per_cycle_ul or volumes.constant_ul"
        )
    if per_cycle is not None:
        if not isinstance(per_cycle, list) or not per_cycle:
            raise ValueError(f"{path}: volumes.per_cycle_ul must be a non-empty list")
        volumes = tuple(float(v) for v in per_cycle)
    else:
        assert constant is not None, "narrowed by (None, None) check above"  # noqa: S101
        if not isinstance(num_cycles, int) or num_cycles <= 0:
            raise ValueError(
                f"{path}: volumes.num_cycles must be a positive int when "
                "volumes.constant_ul is set"
            )
        volumes = (float(constant),) * num_cycles

    if any(v <= 0 for v in volumes):
        raise ValueError(f"{path}: all volumes must be > 0 uL")
    return volumes


def load_experiment_profile(path: str | Path) -> ExperimentProfile:
    """Read a TOML profile from `path`. Raises ValueError on bad schema."""
    p = Path(path)
    with p.open("rb") as f:
        raw: dict[str, Any] = tomllib.load(f)

    name = str(raw.get("name") or p.stem)
    description = str(raw.get("description") or "").strip()
    volumes = _resolve_volumes(raw, p)
    gradient_block = raw.get("gradient") or {}
    gradient_description = str(gradient_block.get("description") or "").strip()

    return ExperimentProfile(
        name=name,
        description=description,
        volumes_ul=volumes,
        gradient_description=gradient_description,
    )
