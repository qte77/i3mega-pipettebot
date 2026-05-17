# Agent Learnings

Gotchas and non-obvious lessons we hit. Keep entries short, dated, and
actionable. Add a new entry every time you'd say "I wish someone had told me
that earlier."

## 2026-05-12 — Aggressive PrusaSlicer speed/quality settings fail on this MK4 setup

Two failed runs so far (1-perimeter draft, then high-speed MK4 profile)
point to the same pattern: pushing past the proven slice baseline causes
either spaghetti, under-extrusion, or detachment. The proven baseline
that consistently works for PLA on this MK4 is:

- `--layer-height 0.3` / `--first-layer-height 0.3`
- `--perimeters 2` (one perimeter peels at print speed)
- `--top-solid-layers 3` / `--bottom-solid-layers 3`
- `--fill-density 12%` `--fill-pattern grid`
- `--perimeter-speed 55` `--external-perimeter-speed 35`
  `--infill-speed 80` `--travel-speed 150` `--first-layer-speed 25`
- `--max-volumetric-speed 11` (stock hotend melt-rate ceiling)
- accelerations 800–1500 mm/s²

**Most-recent failure mode**: bumped to layer 0.4 mm, perimeter 100,
infill 160, max-volumetric 14, accel 1500–2000 — got under-extrusion
mid-print on a 35×90×5 mm flat slab. The volumetric limit is the
binding constraint: the stock hotend can't sustain 14 mm³/s without a
high-flow nozzle / hardened heatbreak.

**Rule**: don't tune slice settings inline for "faster" without
upgrading the hotend first. If a print needs to be faster, change the
**geometry** (less material, lower infill, fewer pieces) rather than
the slicer profile. The MK4 marketing speeds assume Input Shaper + high
flow; we don't have that calibrated here yet.

## 2026-05-11 — ocp-vscode browser viewer is the fastest design-feedback loop we have

`ocp-vscode`'s standalone server (`python -m ocp_vscode` → browser at
`http://127.0.0.1:3939/viewer`) is the highest-bandwidth way to iterate
on build123d parts WITH a non-programmer in the loop. The loop is:

1. Push a part to the viewer: `tools/cad/view.py <part_name>` calls
   `ocp_vscode.show(shape, names=[name])`.
2. User clicks faces in the browser; the bottom-left *Data* tab shows
   each face's area, normal, and bounding box.
3. User describes a change in natural terms ("make the top plate 5 mm
   thick"); agent edits a `_MM` constant in the source.
4. Re-push, re-screencap. Loop is < 5 s per iteration.

The agent can `screencapture -x` the browser to see the same view the
user sees. Use `osascript` to raise Brave (or whatever browser) to the
front first, then capture — otherwise VS Code or another app may be in
focus. Note: the viewer drops state on a new tab/reconnect (shows the
default OCP logo); re-push the part after any reconnect.

**Why this matters**: STEP/STL export gives a "dumb solid" — FreeCAD
won't reverse-engineer sketches from it. The build123d Python source IS
the parametric model. Trying to add click-and-drag CAD editing on top
of STEP files burns hours and doesn't work. The viewer + Python-edit
loop is what's actually productive.

Follow-up to formalize this workflow: see [#69](https://github.com/Lambda-Biolab/i3mega-pipettebot/issues/69).

## 2026-05-11 — PrusaSlicer CLI does NOT auto-arrange multiple STL inputs

Symptom: `prusa-slicer --slice a.stl b.stl c.stl d.stl -o out.gcode`
appears to slice all four, but the output G-code only contains one
piece's toolpath (the rest stacked at origin and got merged or
clipped). Only one part actually prints on the bed; the others are
silently dropped.

Root cause: the CLI loads each STL as a separate object but doesn't
run the GUI's auto-arrange pass. Pieces overlap at origin, and the
slicer's boolean union (or simply the first non-overlapping mesh wins)
produces a single-piece G-code.

**Solution**: bake the bed layout into a SINGLE merged STL via
build123d, with **bbox-aware** positions for each piece:

```python
def position_at_bed(shape, target_x, target_y, target_z_min=0.0):
    bb = shape.bounding_box()
    cx, cy = (bb.min.X + bb.max.X) / 2, (bb.min.Y + bb.max.Y) / 2
    return Pos(target_x - cx, target_y - cy, target_z_min - bb.min.Z) * shape
```

**Subtle gotcha**: do not use the naïve `Pos(target_x, target_y, 0)
* shape`. That puts the part's CAD ORIGIN at the target, not its
center, so parts whose CAD frames don't sit at their bbox center will
overlap each other. We hit this exactly: top plate spans Y=[0, 85] in
CAD (origin at front edge, not center), naïve translation placed it
on top of the lower clamp.

**Second subtle gotcha**: PrusaSlicer auto-centers the *merged* STL on
the bed regardless of input coords, so absolute positions from
`position_at_bed` get shifted. Layout validation by G-code coordinate
ranges must account for this shift (or compute bounds *after* slicing).

The orchestrator lives in `tools/slicer/print_carriage_assembly.py`.

## 2026-05-11 — Minimal PrusaSlicer profile (.ini via `--load`) silently drops bed heating

Symptom: bed never heats during a print sliced with our minimal
`tools/slicer/profiles/pla_plus_02mm.ini`. The profile has
`bed_temperature = 60` in its `[filament]` section, but the resulting
G-code has only `M104` (nozzle) — no `M140`/`M190` (bed).

Root cause: PrusaSlicer's `--load` populates SOME config keys but
silently ignores others when the profile is minimal. Without an
explicit `start_gcode` block, the slicer emits a default start sequence
that does NOT include bed heating. Filament temperatures in the
`[filament]` section don't propagate either; the slicer uses internal
defaults (e.g., 200°C nozzle vs the profile's 210°C).

**Solution**: pass print settings as CLI flags, NOT via the .ini
profile. The flags reliably take effect:

```bash
prusa-slicer --slice \
  --temperature 210 --first-layer-temperature 215 \
  --bed-temperature 60 --first-layer-bed-temperature 65 \
  --start-gcode "M140 S[first_layer_bed_temperature]
M104 S[first_layer_temperature]
G28
M190 S[first_layer_bed_temperature]
M109 S[first_layer_temperature]
G92 E0" \
  -o out.gcode input.stl
```

Use **actual newline characters** in `--start-gcode` (Python string
`"\n"`, NOT `"\\n"` — that latter passes literal backslash-n through to
the .gcode verbatim, which the printer can't interpret). Placeholders
like `[first_layer_bed_temperature]` ARE supported in CLI start_gcode
and get substituted at slice time.

## 2026-05-09 — pyserial 3.5 cannot open 250000 baud on Linux Python builds without `termios.B250000`

Symptom: `serial.Serial(port, 250000, timeout=...)` raises
`termios.error: (22, 'Invalid argument')` from `_reconfigure_port`'s
`tcsetattr` call. Hit in `tools/preflight.py` (#30) and
`examples/showcase_v0_pipette_sim.py` (same root cause, separate script).

Root cause: pyserial 3.5's `BAUDRATE_CONSTANTS` doesn't list 250000, and
the Python `termios` module doesn't expose `B250000` on every build —
it depends on the headers CPython was compiled against, not the distro.
Fedora 43 + Python 3.13 reproduced it; other distros may or may not,
depending on their build config.

**Solution**: open the port at 9600 first, then switch to 250000 via the
Linux-only `TCSETS2 + BOTHER` ioctl. The kernel accepts arbitrary baud
rates this way regardless of which constants Python's `termios` module
exposes. macOS and Windows use the existing pyserial path.

The shared helper lives in `pipettebot.gantry.open_marlin_port()` —
import from there in any new script that opens a Marlin port. Don't
re-implement the ioctl dance per-script.

## 2026-05-08 — Sandbox bind-mounts surface as untracked character-special files

In containerised / sandboxed Claude Code sessions, the user's host shell
and tool dotfiles (`.bashrc`, `.zshrc`, `.gitconfig`, …) and per-session
agent state (`.claude/agents`, `.claude/commands`, `.mcp.json`) get
bind-mounted into the project working tree as **character-special masks**
backed by `/dev/null`. They show as untracked in `git status` even though
they're not real files, and `git stash --include-untracked` errors with
`unsupported file type` because git can't snapshot them.

Pattern (occurrences #19, #24): every fresh sandbox session re-surfaces
the same noise; addressing one set of names doesn't catch the next batch.

**Solution**: gitignore them prophylactically by name. Trailing-slash
patterns (`.idea/`, `.vscode/`) do **not** match the character-special
variant — drop the slash. The full list lives in the `# Per-session
Claude / agent artifacts` and `# Host shell / tool dotfiles` blocks of
`.gitignore`.

**Diagnostic**: `file <path>` reporting `character special (1/3)` →
this is the bind-mount-to-`/dev/null` pattern, not real content.
