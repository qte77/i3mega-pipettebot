"""CLI env-var resolution for pipette experiment profiles, shared across showcases.

Three showcase scripts read ``PIPETTE_PROFILE`` (path to a TOML
experiment profile) and fall back to ``PIPETTE_VOLUME_UL`` for a
constant per-cycle volume. This module centralises that logic so the
three scripts do not drift.

Usage::

    from pipettebot.cli_profile import build_volumes

    volumes_ul, banner = build_volumes(NUM_COLUMNS, "columns")
    print(f"[host] {banner}")
    # ... pass volumes_ul into the per-cycle loop

The ``env=`` injection keeps the helpers trivially testable without
``monkeypatch`` — pass a plain dict in tests.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from pipettebot.profiles import ExperimentProfile, load_profile

if TYPE_CHECKING:
    from collections.abc import Mapping

DEFAULT_VOLUME_UL = 100.0


def resolve_profile(
    env: Mapping[str, str] | None = None,
) -> ExperimentProfile | None:
    """Load the TOML profile referenced by ``PIPETTE_PROFILE``, or ``None`` if unset.

    Empty or whitespace-only values are treated as unset.
    """
    if env is None:
        env = os.environ
    path = env.get("PIPETTE_PROFILE", "").strip()
    if not path:
        return None
    return load_profile(path)


def build_volumes(
    default_count: int,
    unit_label: str,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[tuple[float, ...], str]:
    """Resolve volumes + stdout banner for a showcase.

    If ``PIPETTE_PROFILE`` is set, the profile drives both volumes and
    cycle count (profile length overrides ``default_count``). Otherwise
    use ``PIPETTE_VOLUME_UL`` (or ``DEFAULT_VOLUME_UL``) repeated
    ``default_count`` times.

    ``unit_label`` distinguishes ``"columns"`` (full_pipettebot) vs
    ``"cycles"`` (full_dpette_cycles, full_pipettebot_rows) in the banner.
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
