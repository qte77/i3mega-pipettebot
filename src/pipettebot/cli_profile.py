"""Shared env-var resolution for showcase scripts.

Centralises the `PIPETTE_PROFILE` / `PIPETTE_VOLUME_UL` handling used by
every v0 showcase. Returns `(volumes_ul, banner)` so the caller logs the
schedule consistently.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pipettebot.experiment_profile import load_experiment_profile

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pipettebot.experiment_profile import ExperimentProfile

DEFAULT_VOLUME_UL = 100.0


def resolve_profile(
    env: Mapping[str, str] | None = None,
) -> ExperimentProfile | None:
    """Load the profile pointed to by `PIPETTE_PROFILE`, or None when unset."""
    if env is None:
        env = os.environ
    path = env.get("PIPETTE_PROFILE", "").strip()
    if not path:
        return None
    return load_experiment_profile(path)


def build_volumes(
    default_count: int,
    unit_label: str,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[tuple[float, ...], str]:
    """Return `(volumes_ul, banner)` from env.

    Precedence: `PIPETTE_PROFILE` (overrides count and per-cycle volume)
    > `PIPETTE_VOLUME_UL` x `default_count` > `DEFAULT_VOLUME_UL`.
    """
    if env is None:
        env = os.environ
    profile = resolve_profile(env)
    if profile is not None:
        banner = f"profile {profile.name!r}: {profile.num_cycles} {unit_label}"
        if profile.description:
            banner += f"\n  {profile.description}"
        if profile.gradient_description:
            banner += f"\n  gradient: {profile.gradient_description}"
        return profile.volumes_ul, banner
    volume_ul = float(env.get("PIPETTE_VOLUME_UL", str(DEFAULT_VOLUME_UL)))
    return (volume_ul,) * default_count, (
        f"constant volume {volume_ul:.1f} uL x {default_count} {unit_label}"
    )
