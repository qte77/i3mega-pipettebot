"""Reusable barrel-bore primitive for dPette clamping.

Single source of truth for the round-bore-with-clearance pattern shared
across the i3 carriage mount and dPette cradles. Each call site picks
its own diametral clearance; the primitive standardises how that
clearance gets added to the nominal bore.

D-shaped half-bores (used by the mount's split upper clamp) are built
by calling this primitive and letting the host body's geometry clip
the cylinder — the bore primitive doesn't model the D shape itself.

Origin at bore centre, axis along Z. Caller positions and subtracts
from the host body.

Lives at `tools/cad/barrel_bore.py` (top level) rather than under
`tools/cad/dpette/` to avoid the namespace collision with the installed
`dpette-usb-driver` package — that conflict makes `from dpette.X import
...` resolve to the driver, not the local directory.

The corresponding split-bore primitive for 8-channel barrels has not
been ported from so101 — the i3 mount and multi cradle both grip the
rectangular fixed-tip manifold (78 × 11 mm) rather than a circular
body, so no shared circular primitive applies on that side yet.
"""

from build123d import Cylinder


def make_clamp_bore(
    bore_diameter_mm: float,
    bore_height_mm: float,
    diametral_clearance_mm: float = 0.5,
) -> Cylinder:
    """Cylinder for a round-barrel clamp bore, inflated by clearance.

    `diametral_clearance_mm` is added to the nominal bore diameter
    (so the radial gap is half of that). Default 0.5 mm matches the
    rigid-clamp convention used by the i3 carriage mount (Ø27 barrel,
    Ø27.5 bore). Cradles use 1.0 mm for an easier slide-in fit.
    """
    return Cylinder((bore_diameter_mm + diametral_clearance_mm) / 2, bore_height_mm)
