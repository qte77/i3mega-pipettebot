---
paths:
  - "tools/cad/i3/**/*.py"
---

# i3 Mega print-head payload budget

## Stock AI3M direct-drive carriage has a finite payload

The Anycubic i3 Mega ships with a Titan-style direct-drive extruder on
the print head. Empirically the carriage starts losing steps under
moderate-to-fast XY moves once mounted payload exceeds **~300 g**. This
is a soft limit — exact threshold depends on acceleration settings and
belt tension — but it is the design budget for this v0.

## Every carriage-mounted part declares its mass

CAD scripts under `tools/cad/i3/` build parts that bolt onto the print
head. The mass of those parts directly eats the payload budget.

**Rule**: every `build_*()` function in `tools/cad/i3/` carries a
`# Mass:` comment near the top of the function body, with the estimated
printed mass in grams and the assumed material density (PLA ≈ 1.24 g/cc,
PETG ≈ 1.27 g/cc, TPU ≈ 1.21 g/cc). Compute as `volume_cc * density`
using `shape.volume / 1000.0` for cc.

Example:

```python
def build_carriage_dpette_mount():
    """..."""
    # Mass: ~85g PLA (volume 68.5 cc * 1.24 g/cc), leaves ~215g for dPette
    ...
```

## Tests assert the budget

Tests in `tests/tools/cad/i3/` include an explicit
`assert estimated_mass_g(shape, density="pla") < 300` style check.
Failing this is a hard test failure — the part is unbuildable as
designed.
