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

`<printer>_<material>_<layer>.ini` — e.g. `i3mega_pla_02mm.ini`. New
printers or materials get their own file rather than overrides.

## Per-part profile selection

`validate.py::get_profile()` maps STL filename to profile. Material
overrides (TPU, PETG) are encoded as sets of STL basenames at the top
of `validate.py`, not as inline arguments.
