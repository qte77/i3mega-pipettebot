---
title: "Prusa MK4 + PrusaSlicer workflow notes"
status: "ACTIVE"
updated: "2026-05-17"
---

Workflow notes and CLI quirks discovered while slicing this repo's
labware (deck plate + dpette parts) on a Prusa MK4 with PrusaSlicer
2.9.4. Recommended path for actual prints is the **GUI**, not the
CLI — see "When to use the CLI" below.

## Quick reference

| What | Where |
|---|---|
| Bed dimensions (MK4) | 250 mm (X) × 220 mm (Y) × 220 mm (Z) |
| System preset bundle | `/usr/share/PrusaSlicer/profiles/PrusaResearch.ini` (1.5 MB, 36 MK4 variants) |
| User config dir | `~/.config/PrusaSlicer/` (presets dirs empty by default — GUI reads system bundle) |
| Repo profiles | `tools/slicer/profiles/*.ini` (minimal; documentation + reference only) |
| Repo STL output | `hardware/stl/<area>/<part>.stl` |
| Repo STEP output | `hardware/step/<area>/<part>.step` |
| Network upload to MK4 | PrusaLink HTTP over RJ45 (`tools/slicer/upload_to_prusalink.py`) |
| Offline upload to MK4 | USB-A thumb drive on the printer front |
| Binary G-code (`.bgcode`) | Smaller, MK4 native — use `--binary-gcode` |

## PrusaSlicer 2.9.4 CLI quirks (verified)

These bit us during this work — document so future-us doesn't
re-debug. Tested with `prusa-slicer 2.9.4 (Fedora build)`.

### Quirk 1 — `.ini` profiles don't reliably load via `--load`

The minimal profiles under `tools/slicer/profiles/*.ini` set keys
like `bed_shape`, `binary_gcode`, `gcode_flavor`, `thumbnails`,
`layer_height`, `fill_density`, `temperature`, and the per-feature
speed keys (`perimeter_speed`, `infill_speed`, ...).

**Behavior**: when invoked as `prusa-slicer --load profile.ini …`,
PrusaSlicer silently falls back to **defaults** for most of these
keys. The slicer doesn't error or warn; the output just doesn't
match the profile.

**Confirmed-loaded** via `--load`:

- `nozzle_diameter` (sometimes)
- `printer_model` (sometimes)
- A few filament keys

**Confirmed-NOT-loaded** via `--load`:

- `bed_shape` — falls back to 200 × 200 default
- `binary_gcode` — output stays plain ASCII G-code
- `gcode_flavor` — no MK4 hints in output
- `thumbnails` — no thumbnails block, no preview on MK4 screen
- `layer_height`, `fill_density`, `brim_width` — default values used
- All `*_speed` keys — defaults used (60 / 80 / 130 mm/s)
- `temperature` (filament) — defaults used

**Workaround**: pass every required key as an **explicit CLI flag**.
A working ultra-draft invocation:

```bash
prusa-slicer --binary-gcode --export-gcode \
  --bed-shape 0x0,250x0,250x220,0x220 \
  --gcode-flavor marlinfirmware \
  --thumbnails 220x124/PNG,16x16/PNG \
  --printer-model MK4 \
  --nozzle-diameter 0.4 \
  --layer-height 0.3 --first-layer-height 0.2 \
  --perimeters 2 --fill-density 10% \
  --brim-width 5 \
  --temperature 230 --bed-temperature 55 \
  --filament-type PLA --extrusion-multiplier 0.7 \
  --output OUT.bgcode INPUT.stl
```

### Quirk 2 — preset-by-name (`--printer-profile NAME`) fails

The system preset bundle at
`/usr/share/PrusaSlicer/profiles/PrusaResearch.ini` contains 36 MK4
variants (`Original Prusa MK4 0.4 nozzle`, `… Input Shaper 0.4 nozzle`,
etc.) and hundreds of print/filament presets, but the CLI doesn't
find them by name:

```bash
prusa-slicer --printer-profile "Original Prusa MK4 Input Shaper 0.4 nozzle" \
  --print-profile "0.20mm SPEED @MK4IS 0.4" \
  --material-profile "Prusa PLA" …
# Error: Printer profile '…' wasn't found.
```

Pointing at the system bundle with `--datadir
/usr/share/PrusaSlicer` also fails:

```text
Error: Configuration wasn't found. Check your 'datadir' value.
```

`--datadir` expects a USER data dir shape (`print/`, `printer/`,
`filament/` subdirs containing individual preset `.ini` files), not
the system vendor bundle.

**Workaround**: open the file in the GUI once, save the relevant
preset to the user data dir, then `--datadir ~/.config/PrusaSlicer`
will find it. Or just stick with explicit CLI flags.

### Quirk 3 — "objects outside print volume" exits 0

If the input STL's bounding box extends past the bed, PrusaSlicer
prints `All objects are outside of the print volume.` to stdout and
**exits with code 0**. No G-code is written. `make check_prints` /
`tools/slicer/validate.py` doesn't catch this because the gate
keys on exit code + a hand-picked overhang keyword list.

**Workaround**: pre-translate STLs so `min_xy >= 0` before slicing.
We do this for the deck-plate assembly STL (origin at well-plate
left-front means literal coords go negative). A small build123d
helper:

```python
from build123d import Pos, import_stl, export_stl
mesh = import_stl('hardware/stl/labware/deck_plate_assembly.stl')
shifted = Pos(10, -12.5, 0) * mesh   # move bbox min to (0,0,0)
export_stl(shifted, '/tmp/deck_assembly_for_print.stl')
```

**Pending validate.py fix**: add `"outside of the print volume"`
and `"could not be sliced"` to `OVERHANG_KEYWORDS`, and require an
output file to exist before declaring PASS.

### Quirk 4 — `--center` / `--align-xy` don't reposition reliably

The CLI exposes `--center X,Y` and `--align-xy X,Y` transform
options, but in 2.9.4 they did NOT reposition off-bed STLs to fit
in our tests. Pre-translation (Quirk 3) is the only reliable path.

### Quirk 5 — Input Shaper preset must be in user data dir

The MK4 firmware refuses bgcode that wasn't sliced for Input Shaper
("gcode not sliced for input shaping"). The IS-aware preset
`Original Prusa MK4 Input Shaper 0.4 nozzle` lives in the system
bundle at `/usr/share/PrusaSlicer/profiles/PrusaResearch.ini`, but
neither `--printer-profile NAME` nor `--load <bundle>` can select
it directly from there.

The CLI only finds presets in `~/.config/PrusaSlicer/{printer,print,
filament}/`. PrusaSlicer GUI populates this on first run; the CLI
does not.

**Workaround**: extract the resolved preset (walking the `inherits =
*commonMK4*` chain) and write it as a flat `.ini` to the user data
dir. After that, `--printer-profile "Original Prusa MK4 Input
Shaper 0.4 nozzle"` works and emits the correct M593 + IS-tuned
machine_max_acceleration_* / feedrate / jerk values.

Minimal Python extractor:

```python
import re
from pathlib import Path
BUNDLE = '/usr/share/PrusaSlicer/profiles/PrusaResearch.ini'
USER = Path.home() / '.config' / 'PrusaSlicer'

def parse(p):
    sec, name, buf = {}, None, []
    for line in open(p):
        m = re.match(r'^\[([^\]]+)\]\s*$', line)
        if m:
            if name: sec[name] = buf
            name, buf = m.group(1), []
        else: buf.append(line)
    if name: sec[name] = buf
    return sec

def kv(lines):
    d = {}
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith('#') and '=' in s:
            k, v = s.split('=', 1); d[k.strip()] = v.strip()
    return d

def resolve(sec, full, visited=None):
    visited = visited or set()
    if full in visited: return {}
    visited.add(full)
    body = kv(sec[full])
    inh = body.pop('inherits', None)
    if inh:
        kind = full.split(':',1)[0]
        for parent in re.split(r'[;,]', inh):
            p = parent.strip().strip('"\'')
            if p:
                for k, v in resolve(sec, f'{kind}:{p}', visited).items():
                    body.setdefault(k, v)
    return body

s = parse(BUNDLE)
for kind, name in [
    ('printer', 'Original Prusa MK4 Input Shaper 0.4 nozzle'),
    ('print',   '0.20mm SPEED @MK4IS 0.4'),
    ('filament','Prusa PLA'),
]:
    body = resolve(s, f'{kind}:{name}')
    d = USER / kind; d.mkdir(parents=True, exist_ok=True)
    with open(d / f'{name}.ini', 'w') as f:
        for k, v in body.items(): f.write(f'{k} = {v}\n')
    print(f'wrote {kind}/{name}.ini ({len(body)} keys)')
```

Run once on the workstation (outside any sandbox), then CLI slice
with:

```bash
prusa-slicer --binary-gcode --export-gcode \
  --printer-profile "Original Prusa MK4 Input Shaper 0.4 nozzle" \
  --print-profile   "0.20mm SPEED @MK4IS 0.4" \
  --material-profile "Prusa PLA" \
  --output OUT.bgcode INPUT.stl
```

Could be packaged as `make setup_prusa_presets` (TODO).

### Quirk 6 — `start_gcode` empty by default → printer doesn't auto-heat

Without a loaded preset, PrusaSlicer's `start_gcode` field is empty.
A bgcode sliced via `--load <minimal.ini>` will not contain `M140`
/ `M190` / `M104` / `M109` / `G28` commands, so when the printer
starts the file it does **not** heat the bed or nozzle automatically
— the operator has to set temps and home manually on the printer
screen before the print proceeds.

PrusaSlicer auto-emits a single `M104 S<default>` if it detects no
M104 in the start gcode, but uses the DEFAULT first-layer
temperature (200 °C), not the one you passed via `--temperature`.
There's no auto-emit of M140/M190/G28.

**Workaround**: pass an explicit `--start-gcode` (and `--end-gcode`)
with proper sequencing. Use ANSI-C shell quoting (`$'...\n...'`) so
newlines reach PrusaSlicer literally — `"...\n..."` in plain double
quotes ends up as a single comment line containing literal `\n`
characters, and PrusaSlicer auto-emits its own `M104 S200` *before*
the would-be custom block (which now looks like a comment to it).

Working invocation:

```bash
prusa-slicer --binary-gcode --export-gcode \
  --bed-shape 0x0,250x0,250x220,0x220 \
  --gcode-flavor marlinfirmware --printer-model MK4 \
  --nozzle-diameter 0.4 --layer-height 0.3 --first-layer-height 0.2 \
  --perimeters 2 --fill-density 10% --brim-width 5 \
  --temperature 230 --first-layer-temperature 230 \
  --bed-temperature 55 --first-layer-bed-temperature 55 \
  --filament-type PLA --extrusion-multiplier 0.7 \
  --start-gcode $'M140 S[first_layer_bed_temperature]\nM104 S[first_layer_temperature]\nG28\nM190 S[first_layer_bed_temperature]\nM109 S[first_layer_temperature]\nG1 Z5 F600' \
  --end-gcode   $'G1 Z+10 F300\nG28 X0 Y0\nM104 S0\nM140 S0\nM84' \
  --output OUT.bgcode INPUT.stl
```

The sequence inside the start gcode matters:

1. `M140` (no-wait set bed temp) — bed starts heating
2. `M104` (no-wait set nozzle temp) — nozzle starts heating in parallel
3. `G28` — home while both heat up
4. `M190` (wait for bed) — block until bed is hot
5. `M109` (wait for nozzle) — block until nozzle is hot
6. `G1 Z5 F600` — lift nozzle before extruding so the heated nozzle
   doesn't drag on the bed

PrusaSlicer's placeholder substitution (`[first_layer_temperature]`
etc.) only works if the line is parsed as G-code, which requires
real newlines.

**Related**: `--first-layer-temperature` / `--first-layer-bed-temperature`
are SEPARATE from `--temperature` / `--bed-temperature`. The
auto-emit and the `[first_layer_temperature]` placeholder both use
the first-layer values. Set both pairs to the same value unless you
deliberately want first-layer to differ.

### Quirk 7 — speeds get overridden by cooling logic

Even when `--perimeter-speed 30` is accepted, PrusaSlicer's cooling
logic adjusts per-layer speed based on `cooling`,
`fan-below-layer-time`, and `slowdown-below-layer-time`. The
embedded G-code header shows the requested speed; the actual
movements run slower if layers are estimated short.

For LW-PLA on a 219 × 219 mm footprint at 0.3 mm layer, expect
2-3× slowdown vs the configured perimeter_speed.

## When to use the CLI vs the GUI

- **GUI (preferred for actual prints)**: handles presets, thumbnails,
  arrangement, Input Shaper variants, LW-PLA fine-tuning correctly.
- **CLI (good for batch validation / gates)**: minimum-viable slice
  for `make check_prints`. Don't trust CLI G-code output for actual
  printing without GUI verification.

## Cheat sheet: actual print workflow

1. **Slice in GUI**: open PrusaSlicer GUI, pick "Original Prusa MK4 Input
   Shaper 0.4 nozzle" + a Prusa print profile (e.g. "0.20mm SPEED
   @MK4IS 0.4" for production, "0.28mm DRAFT @MK4IS HF0.4" for draft
   if HF nozzle).
2. **Import STL**: `hardware/stl/labware/deck_plate_<half|assembly>.stl`.
3. **Verify auto-arrangement** puts the part on the bed (GUI does this
   automatically — CLI does not).
4. **Tune for LW-PLA** if loaded: extrusion multiplier ≈ 0.7,
   temperature ≈ 230 °C, perimeter speed 25-30 mm/s.
5. **Slice + save** as `.bgcode` (Configuration → Preferences → Other
   → "Use binary G-code…" must be enabled).
6. **Upload via PrusaLink** (RJ45) or USB thumb drive.

## Estimated print times (MK4 + LW-PLA, this deck plate)

With through-hole cutouts under each labware slot (current design):

| Settings | Time | Filament |
|---|---|---|
| LW-PLA prototype (no cutouts, old) | 10 h 54 m | 25.4 m |
| LW-PLA ultra-draft (with cutouts) | 1 h 40 m | 4.3 m |
| LW-PLA prototype (with cutouts, est.) | ~3 h | ~6 m |

Cutouts saved ~85% of print time. The deck became a window-frame
holding lip walls around openings — labware drops to the heated bed.

## Pending CLI improvements (tracked separately)

- `tools/slicer/validate.py`: add `"outside of the print volume"` and
  `"could not be sliced"` to warning keywords; require output file
  to exist before PASS.
- `_build_slicer_cmd`: forward `.ini` keys as explicit CLI flags so
  the gate actually validates against the configured profile.
- `make slice` recipe: produce a tracked `.bgcode` artifact under
  `hardware/bgcode/<area>/<part>.bgcode` using the working CLI flag
  pattern documented above.

## References

- Prusa MK4 spec: <https://www.prusa3d.com/product/original-prusa-mk4-2/>
- PrusaSlicer 2.9 release notes: <https://github.com/prusa3d/PrusaSlicer/releases>
- PrusaResearch bundle (system): `/usr/share/PrusaSlicer/profiles/PrusaResearch.ini`
- Binary G-code format (bgcode): <https://github.com/prusa3d/libbgcode>
- Repo profiles: [`tools/slicer/profiles/`](../../tools/slicer/profiles/)
- Slicer validator: [`tools/slicer/validate.py`](../../tools/slicer/validate.py)
