---
paths:
  - "tools/cad/**"
  - "tools/slicer/**"
---

# CAD printability gate

## `make check_prints` gates CAD changes

Just as `make validate` gates `src/` changes, `make check_prints` gates
CAD changes. It runs the active slicer (OrcaSlicer first, PrusaSlicer
fallback) over every active STL in `hardware/stl/` and reports overhang,
unsupported region, and bridge warnings.

**Rule**: any PR that adds or modifies a part in `tools/cad/` runs
`make check_prints` locally and either:

- reports `PASS` for the changed parts, or
- explicitly accepts the `WARN` in the PR description with rationale
  (e.g. "tip ejection post needs supports; printable as designed").

`FAIL` blocks merge — it means the slicer rejected the geometry as
unbuildable.

## Skipped parts must be tracked

If a slicer binary is unavailable in the environment, `validate.py`
emits `SKIP` per part. CI must not silently swallow `SKIP` as success;
a `SKIP` count > 0 means the gate did not run.

**Rule**: `make check_prints` exits non-zero when any active part is
`FAIL` or when the active slicer is missing. `WARN` is allowed but
surfaced.
