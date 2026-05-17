---
title: "Motion-profile graphs — ASCII sketches"
status: "DRAFT"
updated: "2026-05-17"
owner: "qte77"
---

ASCII placeholders for the two motion-profile visualization graphs.
These are sketches for the design intent; an SVG/PNG implementation is
tracked in the follow-up issue referenced from the README / CHANGELOG.

Both views are driven by:

- The active `MotionProfile` (SLOW / MID / FAST) from
  `src/pipettebot/motion_profile.py` — supplies M201 (accel caps),
  M203 (feedrate caps), M205 (classic jerk).
- The path constants from a chosen showcase script (e.g. the row tour
  in `examples/showcase_v0_full_pipettebot_rows.py`).

## Graph A — Kinematics per axis (3-panel)

Trapezoidal velocity profile per axis under the active profile, paired
with rectangular accel pulses (+a during ramp-up, 0 at cruise, -a
during ramp-down). Jerk shown as instantaneous v steps at junctions.

```text
+-------------------------+  +---------------------+  +---------------------+
| X axis                  |  | Y axis              |  | Z axis              |
| v [mm/s]      a [mm/s²] |  | (same layout)       |  | (same layout)       |
|  ^             ^        |  |                     |  |                     |
|  |   ___v___   | +--+   |  |                     |  |                     |
|  |  /        \ | |a |   |  |                     |  |                     |
|  | /          \| |+ | +-+ |                     |  |                     |
|  |/            \  +--+ |- |                     |  |                     |
|  +--------------------+|-+|                     |  |                     |
|       trapezoid       t  |                     |  |                     |
+-------------------------+  +---------------------+  +---------------------+
```

Active profile (SLOW / MID / FAST) is annotated on each panel.

## Graph B — 3-view path plot (top + 2 side panels)

Top view (XY plane) of the full tour, plus side panels showing the same
path projected onto X-Z and Y-Z so descents are visible against XY
position. From the operator's perspective: HOME at X=0 is on the left;
reservoir + tip box at X=171 are on the right.

```text
+--------------------------------+  +-------------------+
|  TOP VIEW (X-Y plane, Y up)   |  |  SIDE  (X-Z)      |
|                                |  |   Z ^             |
|   Y                            |  |   | +--\  /-\     |
|   ^                            |  |   | |   \/   \-\  |  <- descents
|   |   * tip box                |  |   | |  bar   |\\  |    into bar,
|   |   *-> reservoir            |  |   | |          \  |    wells, etc.
|   |                            |  |   +----------> X  |
|   |   [] 96-well plate         |  +-------------------+
|   |                            |
|   |   * bar (release)          |  +-------------------+
|   |                            |  |  SIDE  (Y-Z)      |
|   |   * HOME (0,0)             |  |   Z ^             |
|   +-------------> X            |  |   | \   /\        |
+--------------------------------+  |   |  \_/  \___    |
                                    |   +----------> Y  |
                                    +-------------------+
```

Path coloured by time (light → dark) or by phase (pickup / aspirate /
dispense / eject). Side panels are the same trajectory projected onto
X-Z and Y-Z planes so Z(time) can be read against X(time) and Y(time).

## Orientation convention

Side views are from the **front (operator's perspective)**, looking
along −Y. Implication: X=0 (HOME, X-min endstop) is on the left of
side views; X=171 (reservoir, tip box, +X direction) is on the right.

## Implementation notes (for the follow-up tool)

- Pure Python with matplotlib. No hardware needed — kinematic
  simulation under M201/M203/M205.
- Reads bundle constants directly from `pipettebot.motion_profile` so
  the plot always matches what the gantry actually receives.
- Renders SVGs to `hardware/svg/` (gitignored; same convention as the
  STL output of the CAD pipeline).
- Three SVGs: kinematics-per-axis (this file's Graph A),
  three-view path plot (Graph B), and a deck-layout top view (see
  `deck-layout-rows-script.md`).
