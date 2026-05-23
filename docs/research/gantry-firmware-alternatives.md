# Gantry / firmware alternatives — research log

Append-only log of gantry hardware and firmware targets evaluated against the
current Anycubic i3 Mega + stock Marlin pipeline that `src/pipettebot/gantry.py`
assumes. Verdicts may be revisited if upstream state changes (firmware version
bump, community Marlin port lands, board redesign).

Applies to this repo only — gantry choice does not propagate to the sibling
`so101-biolab-automation` (different motion stack). Per-printer verdicts may
imply repo-wide changes (renames, adapter splits) which are called out in the
entry.

## Evaluation criteria

Hard requirements (any failure is a blocker):

- G-code over USB serial control — line-buffered ASCII protocol
- Cartesian kinematics — matches the raw `(x, y, z)` abstraction in
  `PipetteBot.aspirate_at()` / `dispense_at()`; non-Cartesian targets would
  break the deck-frame contract in `docs/deck-layout.md`
- A synchronization primitive — either Marlin-style `M400` or a measurable
  post-motion ack — so `.claude/rules/motion-safety.md` rule #2 ("wait for
  moves before pipetting") is enforceable
- Carriage payload headroom for the dPette+ plus mount
  (cf. `.claude/rules/i3-carriage-payload-budget.md` for the i3 cap of 300 g;
  per-target caps are entry-specific)
- Firmware source or schematics available so bring-up bugs are debuggable

Soft preferences:

- Larger build envelope (more SBS slots, additional reservoirs)
- Stock Marlin (or close enough) so `motion_profile.as_marlin()` and the
  existing `tools/marlin_repl.py`, `tools/preflight.py`, `tools/diagnose_axis.py`
  bring-up scripts apply without per-printer forks
- Cheap and available used — aligns with the project's resource-constrained
  researcher persona in `docs/UserStory.md`
- Wide community support (replacement parts, slicer profiles)

## Entries

### 2026-05-23 — Geeetech A30 (HW v3.3, fw v1.37.58)

Evaluated as a second gantry target alongside the Anycubic i3 Mega. The A30
has a notably larger build envelope (~320 x 320 x 420 mm vs ~210 x 210 x 205
mm), which would expand the deck-frame from one SBS plate + tip box + reservoir
to multi-plate workflows. Two firmware paths exist: stock Smartto and a
community Marlin port. They score very differently.

#### Stock Smartto firmware (Geeetech)

- **What:** Geeetech's in-house, open-source firmware. Versioning matches the
  user-supplied `v1.37.58`. Not a Marlin fork — designed from scratch around
  the STM32 CPU. Source at `github.com/Geeetech3D/Smartto`.
- **Board:** GTM32 mini s (STM32F103R, 32-bit ARM). The mainboard is
  different from the GT2560 (AVR) used in Geeetech's Prusa-class printers.
- **License:** open-source per Geeetech's distribution (no SPDX header at the
  repo root, but redistributed by Geeetech as such). Confirm before any
  redistribution.
- **G-code surface:** `G0 G1 G4 G20 G21 G28 G90 G91 G92 M17 M18 M84 M104 M105
  M106 M107 M109 M110 M114 M115 M117 M119 M140 M190 M220` per Geeetech staff
  reply on the forum. **Notably missing in older releases: `M400`, `M203`,
  `M201`, `M204`, `M205`.** Whether v1.37.58 specifically adds any of these
  was not confirmed — needs a `grep` of the Smartto repo at the matching tag.
- **Baud rate:** not confirmed from public docs. STM32 firmware typically
  defaults to 115200. The i3 Mega runs at 250000.
  `src/pipettebot/gantry.py::open_marlin_port()` would need a per-target
  baud constant.
- **Impact on current rules:**
  - `motion-safety.md` rule #2 (always `M400` between move and pipette
    operation) is unenforceable on stock Smartto. Mitigation paths: poll
    `M114` until coords stabilize within a tolerance band, or characterize
    whether Smartto's `ok` is issued post-motion (Marlin's is post-planning).
    Until measured on hardware, the rule cannot be guaranteed.
  - `MotionProfile.as_marlin()` ([ADR 0003](../adr/0003-motion-profile-bundled-constants.md))
    emits `M203 M201 M204 M205` — all four are no-ops on stock Smartto. The
    profile bootstrap would have to be skipped or moved into firmware
    config (out of scope for v0).
- **Verdict:** **TRACK with adapter.** Plausible v0 target if (a) the baud
  and `ok`-timing unknowns are resolved by reading Smartto source at the
  v1.37.58 tag, and (b) `GcodeGantry` is split behind a `GantryProtocol`
  with `MarlinGantry` and `SmarttoGantry` implementations, mirroring the
  `_ArmController` Protocol pattern already used for so101 (PR #133).
  Repo rename `i3mega-pipettebot` -> `pipettebot` and example rename
  `showcase_v0_pipette_sim.py` -> `showcase_v0_dpette_i3.py` + new
  `showcase_v0_dpette_a30.py` would follow naturally from the split. ADR
  required.

#### Community Marlin 2.x port (TheThomasD/GeeetechA30T)

- **What:** Community effort to port Marlin 2.x to the A30T (twin-extruder
  A30 variant). Repo at `github.com/TheThomasD/GeeetechA30T`. Targets the
  GTM32_103_V1 board variant — board layout is close enough to the GTM32
  mini s on the standard A30 that the port is plausible, but not identical.
- **License:** Marlin's GPLv3 — incompatible with this project's Apache-2.0
  for any in-tree redistribution. Acceptable as a flashable artifact the
  user loads themselves; not acceptable as a vendored submodule.
- **Status:** Out-of-tree. Not in upstream Marlin. A separate community
  request (`Geeetech3D/Diagram#1`) asks for upstream support of the GTM32
  mini and pro boards; not merged.
- **Impact on current rules:** If the user flashes Marlin successfully, the
  printer becomes a near-drop-in for `MarlinGantry`. `M400` and `M2xx` work;
  `motion_profile` applies; baud aligns with the firmware build's
  `BAUDRATE`. The risk shifts to flashing reliability and to brick risk on a
  GTM32 board with no JTAG header populated by default.
- **Verdict:** **SKIP for v0; TRACK as a Stage-1+ option.** Blocked by
  AGENTS.md rule #4 ("no firmware modifications in v0"). Revisit once
  `AGENT_REQUESTS.md` opens a firmware track and an ADR is in place. If
  pursued, the gantry layer stays single-class (Marlin) and no adapter
  split is needed for this path.

#### Unknowns to resolve before adopting

1. ~~Smartto baud rate at the v1.37.58 tag.~~ **Confirmed 115200** via live
   `M115` over USB on the user's printer (see 2026-05-23 bring-up entry).
2. ~~Does Smartto's `ok` post-date motion completion, or only planning?~~
   **Moot.** `M400` is supported (see capability probe), so the standard
   ack-after-flush pattern works identically to Marlin.
3. ~~Does fw 1.37.58 add `M400`?~~ **Yes**, plus `M203` / `M204` / `M205` /
   `M501` / `M503` — full Marlin-style motion-tuning surface. The
   Geeetech forum G-code list (predating 1.37.58) was stale.
4. ~~Can `M115` capabilities be parsed at startup for feature detection?~~
   **No.** Live `M115` returns five fields (`MACHINE_TYPE`, `UUID`,
   `FIRMWARE_NAME`, `PROTOCOL_VERSION`, `EXTRUDER_COUNT`) with no `Cap:`
   lines. Mooted by item 3 — the adapter does not need capability
   detection when the relevant commands are confirmed supported.
5. A30 carriage payload budget — measure or source from Geeetech docs.
   Drives a sibling rule to `.claude/rules/i3-carriage-payload-budget.md`
   and a parallel CAD subtree at `tools/cad/a30/`.

### 2026-05-23 — A30 live bring-up over USB (Smartto v1.xx.58)

Hardware-confirmed observations from a read-only diagnostic session
(`tools/smartto_probe.py`) on the user's A30 at `/dev/ttyUSB0`. Updates
several speculative items above.

- **Baud:** 115200 on first attempt; sweep order
  `115200 → 250000 → 57600 → 9600` did not need to fall back.
- **M115 reply:**
  `MACHINE_TYPE:A30 UUID:181010A3000515A FIRMWARE_NAME:V1.xx.58
  PROTOCOL_VERSION:V1.0 EXTRUDER_COUNT:1` followed by `ok`. The patch
  byte renders as a literal `xx` placeholder — likely a Smartto reporting
  quirk, not a firmware version mismatch (LCD shows 1.37.58).
- **M114 reply:** `X:0.000 Y:0.000 Z:0.000 E:0.000` followed by `ok`.
  Standard Marlin-compatible coordinate format.
- **M119 reply (both polls):**
  `x_min:OPEN  x_max:OPEN  y_min:OPEN  y_max:OPEN  z_min:TRIGGERED
  z_max:OPEN` followed by `ok`. **z_min did not change state when the
  operator manually engaged the Z sensor.**
- **Implication for Z homing:** the Smartto firmware reads `z_min` as
  permanently triggered. Two failure modes produce this signature and
  cannot be distinguished from the M119 output alone:
  (a) A30 homes via a separate Z-probe (BL-Touch / 3DTouch / inductive)
  that consults a different pin from the z_min switch; the probe never
  triggers, Z dives indefinitely, and the `z_min:TRIGGERED` we see is a
  floating-pull-up on an unused mechanical-switch input.
  (b) The z_min wire is physically disconnected / shorted, leaving the
  pin in a default-active reading; firmware finds no untriggered state to
  back off from during homing and the routine dives.
  Disambiguation requires visual inspection of the print head for a
  probe assembly.
- **Update from in-session bring-up (same date):** the Z sensor is a
  frame-mounted inductive proximity probe (red power LED on the sensor
  body, target plate on the Z lead-screw nut) — *not* head-mounted.
  Earlier head-removal hypothesis was wrong; print-head removal does
  not remove the Z reference on this printer. Operator confirmed the
  sensor correctly triggers at Z=0 (the LED + M119 z_min:TRIGGERED match
  the physical carriage position), yet `G28 Z` continues to drive Z
  down past the trigger point. Endstop hardware and signal-to-board
  path are therefore both working; the failure is in Smartto's homing
  routine itself. Most likely cause: the firmware build expects a
  separate `Z_PROBE` pin (BL-Touch / A30-Pro variant) that this stock
  A30 does not have wired, so `G28 Z` watches an input that never
  transitions while the working `z_min` switch is ignored by the homing
  state machine. Cannot be fixed without a firmware rebuild (blocked by
  AGENTS rule #4).
- **`G28 Z` is unusable on this build; substitute polled descent.** The
  A30 gantry layer must never call `G28 Z` directly. Replacement
  recipe, using only commands the live probe confirmed Smartto handles
  (`G1`, `M119`, `G92`, `G90/G91`):
  ```
  G91
  loop:
    G1 Z-1 F300
    M119          ; parse z_min state
    if z_min:TRIGGERED -> break
  G90
  G92 Z0
  ```
  This makes `home()` semantics genuinely diverge between
  `MarlinGantry` (M400 + G28) and `SmarttoGantry` (polled descent +
  G92) — load-bearing argument for the adapter split rather than a
  dialect flag inside a single class.
- **Print-head removal is project policy, not optional.** Same principle
  as the i3 Mega (cf. memory: "X carriage hot end removed — dPette + light
  printed holder ... lighter than stock"). On the i3, this is non-fatal
  because the Z-min microswitch is frame-mounted; on the A30 it removes
  the Z homing reference entirely. The two printers are not symmetric on
  this point — any A30 bring-up must address Z origin without a head.
- **Z origin paths for v0 (no firmware mods per AGENTS rule #4):**
  - **Path A — manual `G92 Z0` per session.** Home laterals only
    (`G28 X Y`), jog Z to a known reference, set origin. Zero hardware.
    Operator overhead: one touchoff per power cycle.
  - **Path B — frame-mounted Z-min microswitch.** ~$1 part wired to the
    Smartto `z_min` input, bracket under a new `tools/cad/a30/`. Restores
    `G28 Z`. Contingent on confirming `G28 Z` consults the `z_min` pin
    and not a separate probe input — answerable with a one-cable test.
  - Recommendation: Path A first, Path B if/when per-session `G92`
    becomes operationally annoying.
- **Adapter implication:** Smartto's `ok` terminator is Marlin-compatible,
  so the existing `_send` / `wait_for_moves` ack pattern in
  `src/pipettebot/gantry.py` is reusable verbatim. `M400` is confirmed
  supported (see capability probe below). The bigger gap is the absence
  of `Cap:` lines in `M115` — runtime feature detection is off the table.
- **Capability probe (tools/smartto_probe.py phase 3):** all six tested
  commands replied `ok`. Verdict table:

  | Command                    | Verdict     | Notes                                          |
  |----------------------------|-------------|------------------------------------------------|
  | `M503` (dump settings)     | SUPPORTED   | Bare `ok`, no dump payload — acknowledged but emits nothing. |
  | `M400` (wait moves)        | SUPPORTED   | Bare `ok` — pattern matches Marlin.            |
  | `M203 X500 Y500 Z20`       | SUPPORTED   | Replies `max_feedrate_set_ok` before `ok`.     |
  | `M204 P1000`               | SUPPORTED   | Replies `acceleration_set_ok` before `ok`.     |
  | `M205 X10 Y10 Z0.4`        | SUPPORTED   | Replies `max_jerk_set_ok` before `ok`.         |
  | `M501` (EEPROM load)       | SUPPORTED   | Bare `ok` — restores persisted values.         |

  **Direct consequence:** `motion_profile.as_marlin()` ([ADR 0003](../adr/0003-motion-profile-bundled-constants.md))
  applies to the A30 verbatim. The SLOW/MID/FAST bundled profiles all
  work without modification. The "speed up the A30" question reduces to
  `MOTION_PROFILE=fast` plus, optionally, a custom A30 profile tuned for
  the lighter (no-extruder) carriage.

  **Smartto-specific quirks:** (a) `M503` is a syntactic no-op — accepts
  the command but emits no settings dump, so current motion caps cannot
  be read back. (b) Setters emit a human-readable confirmation string
  (`<param>_set_ok`) before `ok`; the ack-based wait pattern still
  terminates correctly but anyone parsing output for diagnostics should
  expect these.

  **Architecture revision:** the MarlinGantry/SmarttoGantry adapter
  split argued for above is now overkill. The two printers diverge on
  three fields only — default baud (250000 vs 115200), homing strategy
  (`full_g28` vs `xy_then_polled_z`), and capability-probe metadata —
  so a single `GcodeGantry` with a `GantryFlavor` config dataclass is
  cleaner than two parallel classes. ADR should reflect this when
  drafted.
- **Live motion validation (same-session REPL test).** With caps raised
  (`M203 X500 Y500 Z20`, `M204 P1000`, `M205 X10 Y10 Z0.4`) and origin
  declared (`G28 X Y` then `G92 Z0`), `G0 X50 Y50 F6000` executes
  cleanly. Repeatable across re-homes. This confirms the entire v0
  motion path is functional on the A30 without firmware modifications;
  the gantry layer for this printer is unblocked. Additional Smartto
  quirks observed live:
  - `G28 X Y` reports the homed positions inline (`X:0.000` /
    `Y:0.000`) before `ok`. Marlin does not. Reply parsers that look
    only for `ok` are unaffected; parsers extracting positions need
    a separate `M114` regardless.
  - `G1 X Y` with no parameter values is silently accepted as a no-op
    (returns `ok` with no motion). Typo'd motion commands will not
    raise errors — script-side validation matters more than on Marlin.
- **v0 operational runbook (per session, no automation needed):**
  1. Connect at 115200 (`tools/smartto_repl.py` or equivalent).
  2. `G28 X Y` — lateral home.
  3. Manually jog Z to the desired origin (visually or by physically
     placing the carriage), or wait for the inductive sensor to read
     `z_min:TRIGGERED` via `M119`.
  4. `G92 Z0` — declare Z origin.
  5. `M203 X500 Y500 Z20`, `M204 P1000`, `M205 X10 Y10 Z0.4` — raise
     motion caps (or apply `MOTION_PROFILE=fast` once gantry layer
     supports the A30).
  6. Ready for scripted XYZ motion.
  No `G28 Z` at any point. Polled descent recipe deferred until an
  unattended use case justifies the automation.

## Future entries

Subsequent research adds a dated H3 entry above this section. Keep verdict
labels in plain ASCII (ADOPT / SUPPLEMENT / TRACK / SKIP) so they grep
cleanly.
