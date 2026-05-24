"""Motion-profile factors for the i3 Mega gantry bootstrap.

Three named profiles (`slow` / `mid` / `fast`) selectable at runtime
via the `MOTION_PROFILE` env var. Each profile renders to four M-codes
(M203 / M201 / M204 / M205) sent at the bootstrap of every gantry-using
example script.

Usage in examples::

    from pipettebot.motion_profile import select_profile

    profile = select_profile(os.environ.get("MOTION_PROFILE"))
    if profile is None:
        # opt-out: Marlin keeps RAM/EEPROM motion settings as-is
        ...
    else:
        for cmd in profile.as_marlin():
            gsend(link, cmd, gcode_out=gcode_out)

`MID` is the default (returned when env is unset). Empty string or
`"off"` returns ``None`` (opt-out — Marlin keeps RAM/EEPROM motion
settings as-is). Unknown names raise ``ValueError`` with the valid
set listed in the message.

Profile semantics
-----------------

Profiles scale by exact factor of 2x: SLOW x2 = MID, MID x2 = FAST.
MID is the anchor (operator-validated baseline); SLOW halves accel +
jerk for cautious runs, FAST doubles them for time-critical tours.

- **MID** (default): liquid-handling friendly. Z accel held at the
  leadscrew-friendly floor of 200 mm/s² (balances dive speed with
  leadscrew + cantilever shock). X/Y accel kept careful (600 / 800
  mm/s²) to limit plate slosh on Y and tip-pendulum + droplet shed
  on X. Tight classic jerk. This is what every showcase script gets
  when MOTION_PROFILE is unset.

- **SLOW** (MID / 2): extra-gentle. Z accel 100, X/Y accel 300/400,
  jerk 1.5/2.5/0.1. Use for first-time runs on a new fixture, very
  viscous reagents, or any time you want the gantry to look obviously
  cautious.

- **FAST** (MID x2): quicker tours. Z accel 400, X/Y accel 1200/1600,
  jerk 6/10/0.4. Use once you know the deck geometry is solid and
  liquid surface quality is acceptable — saves cycle time at the cost
  of more aggressive motion (more meniscus disturbance, more
  tip-pendulum swing, harsher leadscrew starts).

Feedrate caps (M203 X500 Y500 Z20) are shared across all profiles —
they reflect the leadscrew mechanical limit on Z and a reasonable XY
cruise speed, not a tuning choice. The dialed lever is per-axis accel
(M201) and classic jerk (M205).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotionProfile:
    """Marlin motion profile — feedrate caps, per-axis accel, classic jerk.

    Feedrate caps (M203) are shared across SLOW/MID/FAST by default; the
    dialed lever is `accel_*` (M201) and `jerk_*` (M205). The dataclass
    is frozen so profile constants are immutable at runtime.
    """

    name: str
    accel_x: int
    accel_y: int
    accel_z: int
    accel_default: int
    jerk_x: float
    jerk_y: float
    jerk_z: float
    feed_x: int = 500
    feed_y: int = 500
    feed_z: int = 20
    jerk_e: float = 0.0

    def as_marlin(self) -> tuple[str, str, str, str]:
        """Render as the four bootstrap M-code strings: M203, M201, M204, M205."""
        return (
            f"M203 X{self.feed_x} Y{self.feed_y} Z{self.feed_z}",
            f"M201 X{self.accel_x} Y{self.accel_y} Z{self.accel_z}",
            f"M204 P{self.accel_default} R{self.accel_default} T{self.accel_default}",
            f"M205 X{self.jerk_x:g} Y{self.jerk_y:g} Z{self.jerk_z:g} E{self.jerk_e:g}",
        )


# SLOW / MID / FAST scale by exact 2x. MID is the operator-validated
# baseline; SLOW = MID/2, FAST = MID*2. Half/double makes the difference
# obvious on the bench and keeps the relative spacing predictable for
# anyone tuning per-leg feedrates inside these caps.
SLOW = MotionProfile(
    name="slow",
    accel_x=300,
    accel_y=400,
    accel_z=100,
    accel_default=300,
    jerk_x=1.5,
    jerk_y=2.5,
    jerk_z=0.1,
)
MID = MotionProfile(
    name="mid",
    accel_x=600,
    accel_y=800,
    accel_z=200,
    accel_default=600,
    jerk_x=3,
    jerk_y=5,
    jerk_z=0.2,
)
FAST = MotionProfile(
    name="fast",
    accel_x=1200,
    accel_y=1600,
    accel_z=400,
    accel_default=1200,
    jerk_x=6,
    jerk_y=10,
    jerk_z=0.4,
)

PROFILES: dict[str, MotionProfile] = {"slow": SLOW, "mid": MID, "fast": FAST}
DEFAULT_PROFILE = MID

_OPT_OUT = {"", "off"}


def select_profile(env_value: str | None = None) -> MotionProfile | None:
    """Pick a bundled motion profile by name (case-insensitive, whitespace-trimmed).

    Returns:
        - `DEFAULT_PROFILE` (`MID`) when `env_value` is `None` (env unset).
        - `None` for opt-out (`""` or `"off"` after trim+lowercase).
        - The named profile from `PROFILES` otherwise.

    Raises:
        ValueError: if the name is non-empty and not in `PROFILES`.
    """
    if env_value is None:
        return DEFAULT_PROFILE
    name = env_value.strip().lower()
    if name in _OPT_OUT:
        return None
    if name not in PROFILES:
        valid = sorted(PROFILES)
        raise ValueError(
            f"Unknown motion profile {name!r}; valid: {valid} or '' / 'off' to skip"
        )
    return PROFILES[name]
