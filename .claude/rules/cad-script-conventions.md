---
paths:
  - "tools/cad/**/*.py"
---

# CAD script conventions

## Each script exports `build_*()` functions

Files under `tools/cad/<area>/*.py` are loaded dynamically by
`tools/cad/render.py` via `parts.json`. The manifest names a `build_func`
per part — that function must exist as a top-level callable in the
referenced script.

**Rule**: every CAD script exposes one or more `build_*()` functions
that take no required arguments and return a `build123d.Solid`,
`build123d.Compound`, or an iterable of shapes that can be wrapped into
a Compound.

## No I/O, no prints, deterministic

`render.py` calls `build_*()` once per part and may cache the result.
Side effects (file writes, network, RNG) break caching and reproducibility.

**Rule**: CAD scripts must not:

- read or write files (rendering is `render.py`'s job)
- call `print` or log (the orchestrator handles output)
- use randomness or wall-clock time
- depend on environment variables

## Magic numbers carry units and rationale

All linear dimensions are in **mm**. Anything that looks like a magic
number (clearance, wall thickness, bore diameter) needs a one-line
comment with the source — measured value, datasheet reference, or SBS
labware spec.

**Rule**: numeric constants get a unit suffix in their name (`WALL_MM`,
`BORE_D_MM`) or a trailing comment naming the source.
