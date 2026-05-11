"""Measured-from-hardware constants for the i3 Mega + dPette+ 8-channel build.

Single source of truth for every dimension that came from physical
calipers / scale / ruler measurements. Design-time geometry constants
(wall thicknesses, clearance offsets, post placement, etc.) live in
their respective build scripts (e.g. `i3/carriage_dpette_mount.py`).

CAD scripts import these directly — `from measurements import …` — so
a change here propagates to every consumer without duplication.

All units mm unless suffixed otherwise.
"""

from __future__ import annotations

# ============================================================================
# Carriage — i3 Mega horizontal head-mount plate (per user calipers)
# ============================================================================

HPLATE_W_MM = 63.0  # left ↔ right
HPLATE_D_MM = 70.0  # front ↔ back
HPLATE_T_MM = 2.0  # plate thickness (steel)

# 4-hole cluster on the horizontal plate. Sits in the rear half:
#   front-edge → front row : 45 mm
#   front row  → back row  : 13 mm
#   back row   → back edge : 12 mm  (= 70 − 45 − 13, derived)
SCREW_PITCH_X_MM = 21.0  # 4-hole horizontal spacing, centre-to-centre
SCREW_PITCH_Y_MM = 13.0  # 4-hole vertical spacing, centre-to-centre
SCREW_HOLE_D_MM = 4.5  # M4 clearance (carriage hole measured at 4.0 mm)
SCREW_THREAD = "M4"

HOLE_FROM_LEFT_MM = 22.0  # plate left edge to leftmost hole column
HOLE_FROM_RIGHT_MM = 20.0  # plate right edge to rightmost hole column
HOLE_FROM_FRONT_MM = 45.0  # plate front edge to front hole row
HOLE_FROM_BACK_MM = 12.0  # derived: HPLATE_D − HOLE_FROM_FRONT − SCREW_PITCH_Y

# ============================================================================
# Carriage — vertical plate top (scheme b "L-bracket" reinforcement only)
# ============================================================================

VPLATE_TOP_HOLE_PITCH_MM = 28.0  # 2 holes on vertical plate top, centre-to-centre
VPLATE_TOP_HOLE_D_MM = 4.0  # likely M4 (matches horizontal plate)
VPLATE_TOP_OFFSET_MM = 27.5  # vertical from horizontal-plate top up to these holes
VPLATE_TOP_X_OFFSET_MM = 0.0  # centred over horizontal plate's 4-hole pattern

# ============================================================================
# Pipette — DLAB dPette+ 8-channel (per user calipers / kitchen scale)
# ============================================================================

PIPETTE_HEIGHT_MM = 230.0  # bare body, fixed-tip cones to top
PIPETTE_MASS_G = 250.0  # weight without tips

# Fixed-tip manifold (rectangular section at the very bottom of the body).
# Lower clamp grips here. 8 fixed tip cones extend below this manifold.
LOWER_CLAMP_W_MM = 78.0  # X
LOWER_CLAMP_D_MM = 11.0  # Y
LOWER_CLAMP_H_MM = 5.0  # Z (vertical extent of the manifold itself)

# Round upper barrel — narrow cylindrical section for the upper clamp.
UPPER_CLAMP_BORE_D_MM = 27.0  # Ø27 mm round
UPPER_BARREL_HEIGHT_MM = 15.0  # vertical extent of the round section
UPPER_TO_LOWER_SEPARATION_MM = 50.0  # axis-to-axis between clamps

# Disposable tips extend below fixed cones when mounted.
TIP_EXTENSION_MM = 50.0  # 300 µL polypropylene tip; ~50 mm reach
TIPS_MASS_G = 3.0  # 8 mounted tips combined

# Tips per mounted assembly count for the budget.
PIPETTE_FULL_HEIGHT_WITH_TIPS_MM = PIPETTE_HEIGHT_MM + TIP_EXTENSION_MM  # 280 mm

USB_PORT_LOCATION = "back"  # rotatable 360° via top section
USB_PORT_CLEARANCE_MM = 10.0  # cable strain-relief envelope

# ============================================================================
# Printer envelope — Anycubic i3 Mega chassis (stripped, 3-axis motion only)
# ============================================================================

Z_CARRIAGE_TO_BED_AT_Z0_MM = 19.0  # bare carriage face to bed surface at Z_axis=0
Z_BED_TO_XFRAME_TOP_MM = 290.0  # bed surface up to the printer X-frame top
XFRAME_BEHIND_CARRIAGE_FACE_MM = 25.0  # X-frame top is 25 mm behind carriage front in Y

# ============================================================================
# Material — printed mount
# ============================================================================

PLA_DENSITY_G_PER_CC = 1.24
PETG_DENSITY_G_PER_CC = 1.27
TPU_DENSITY_G_PER_CC = 1.21

# ============================================================================
# System payload budget — gates every carriage-mounted print
# ============================================================================

AI3M_PAYLOAD_CAP_G = 300.0  # empirical, before XY missed-step threshold
