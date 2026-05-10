---
paths:
  - "tools/slicer/**"
  - "tools/cad/**"
---

# Slicer profile source of truth

## All settings live in `tools/slicer/profiles/*.ini`

OrcaSlicer is the default slicer; PrusaSlicer is the optional fallback.
Both consume the same `.ini` profile schema, so one set of profiles
serves both.

**Rule**: `tools/slicer/validate.py` and the `make check_prints` recipe
**never** pass slicer settings inline. No `--layer-height`,
`--fill-density`, or any other tuning flag belongs in code, Make
recipes, or CI. Profiles in `tools/slicer/profiles/*.ini` are the
single source of truth.

## Profile naming

`<material>_<grade>_<layer>.ini` — e.g. `pla_plus_02mm.ini`,
`tpu_95a_02mm.ini`. The fabrication printer is a Prusa MK3S+-class
machine (220 × 220 mm bed); the stripped i3 Mega itself doesn't print.
New materials get their own file rather than overrides.

## Per-part profile selection

`validate.py::get_profile()` maps STL filename to profile. Material
overrides (TPU, PETG) are encoded as sets of STL basenames at the top
of `validate.py`, not as inline arguments.
