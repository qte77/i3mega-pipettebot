---
paths:
  - "tools/cad/i3/**/*.py"
---

# i3 Mega print-head payload budget

## Canonical rule

> Total carriage payload (mount + pipette + tips) must stay below 300 g.

The Anycubic i3 Mega (AI3M) carriage starts losing steps under XY
acceleration once payload exceeds ~300 g empirically — varies with belt
tension and acceleration. Worked example for the dPette+ 8-channel
target lives in [`docs/3d-parts.md`](../../docs/3d-parts.md): 250 g
pipette + 3 g tips → ~47 g headroom for the printed mount.

## Every carriage-mounted part declares its mass

**Rule**: every `build_*()` in `tools/cad/i3/` carries a `# Mass:`
comment with estimated printed mass in grams and assumed density
(PLA ≈ 1.24 g/cc, PETG ≈ 1.27 g/cc, TPU ≈ 1.21 g/cc). Compute as
`shape.volume / 1000.0 * density`.

Example:

```python
def build_carriage_dpette_mount():
    """..."""
    # Mass: ~40g PLA (volume 32 cc * 1.24 g/cc).
    # Combined with 250 g dPette+ + 3 g tips = 293 g, under the 300 g cap.
    ...
```

## Tests assert the system budget

Tests in `tests/tools/cad/i3/` assert the **total system mass** is
under the cap, not just the printed shape:

```python
PIPETTE_MASS_G = 250  # dPette+ 8-channel
TIPS_MASS_G    = 3    # 8 x 300 µL polypropylene tips
assert estimated_mass_g(shape, density="pla") + PIPETTE_MASS_G + TIPS_MASS_G < 300
```

Failing this is a hard test failure — the part is unbuildable as
designed under the AI3M payload limit.
