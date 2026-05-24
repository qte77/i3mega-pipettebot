# AGENTS.md — i3mega-pipettebot

Single source of truth for agents working in this repo. `CLAUDE.md` and
`GEMINI.md` redirect here.

## Claude Code Infrastructure

- Doc hierarchy: AGENTS.md → AGENT_LEARNINGS.md, AGENT_REQUESTS.md, CONTRIBUTING.md, CHANGELOG.md, `docs/adr/NNNN-*.md` (architecture decisions), `docs/research/*.md` (research log; append-only)
- Skills are loaded from the user-level marketplace `qte77-claude-code-plugins`. No repo-local `.claude/skills/`.
- Repo-local rules live in `.claude/rules/` and apply to every session in this directory.

## Core Rules & AI Behavior

1. **Delegate liquid handling to `dpette-usb-driver`.** Never re-encode
   the 6-byte serial protocol here — import `dpette.DPetteDriver` and
   call its public methods. See `.claude/rules/pipette-delegation.md`.
2. **Wait for moves before pipetting.** Always `gantry.wait_for_moves()`
   (M400) between a `move_to(...)` and any `aspirate(...)` /
   `dispense(...)`. Marlin's planner queue is otherwise still draining.
   See `.claude/rules/motion-safety.md`.
3. **Tip above liquid before dispense.** dPette's B3 blow includes a
   piston return that draws extra liquid if the tip is submerged. Raise
   Z to travel altitude before any `dispense_at(...)`.
4. **No firmware modifications in v0.** Stock Marlin only. All firmware
   work (Stage 1+) is in AGENT_REQUESTS.md and must not be merged to
   `main` without an ADR.
5. **Topical commits with squash-merge.** Branch protection rejects merge
   commits. Use `git merge --squash` or PR squash.

## Decision Framework

| Question                                        | Answer for v0                                                    |
|-------------------------------------------------|------------------------------------------------------------------|
| Where does new code go?                         | `src/pipettebot/`. Six modules: `gantry`, `bot`, `experiment_profile`, `motion_profile`, `cli_profile`, `__init__`. |
| Where do experiment profiles live?              | `examples/experiment_profiles/*.toml`; loader in `src/pipettebot/experiment_profile.py`. See issue #79. |
| Where do motion profiles live?                  | Bundled Python constants in `src/pipettebot/motion_profile.py` (slow/mid/fast). `MOTION_PROFILE` env selects; default `mid`; `''` or `off` opts out. See [ADR 0003](docs/adr/0003-motion-profile-bundled-constants.md). |
| Where does deck geometry live?                  | Deferred. Caller passes raw `(x, y, z)` in v0.                   |
| How is dpette imported?                         | Git dep, pinned to a commit SHA before v0.0.1 tag.               |
| Where do hardware experiments go?               | `tools/` — diagnostics (`preflight.py`, `diagnose_axis.py`, `gantry_repl.py`, `gantry_probe.py`), CAD (`tools/cad/`), slicer (`tools/slicer/`). Logs to `captures/`. `gantry_repl` and `gantry_probe` auto-detect firmware via `pipettebot.devices.discover`; replace the older `marlin_repl` / `smartto_repl` / `smartto_probe` trio. |
| Where does SO-101 orchestration live?           | `src/pipettebot/so101/` — `orchestrator.py` (named-position playback after the i3 homes) + `capture_position.py` (teaching CLI). Composition over `so101.DualArmController`; opt-in via `SO101_CONFIG` env. Optional `[orchestrator]` extra; sequence constant hardcoded for v0. See issue #120 and the `_ArmController` Protocol refactor in #133. |
| What goes in AGENT_REQUESTS.md?                 | Anything deferred — features, ADRs, hardware photos, firmware tracks. |

## Architecture Overview

```text
examples/showcase_v0_i3_pipette_sim.py
        │
        ▼
raw pyserial @ 250000 baud   ──► /dev/cu.usbserial-*  Marlin (Anycubic stock / AI3M)
        │
        └─ optional tee       ──► .gcode file for SD replay

src/pipettebot/                        (library, used by examples & tests)
    ├── PipetteBot                    ──► aspirate_at(x,y,z,vol), dispense_at(x,y,z), home()
    ├── GcodeGantry                   ──► home(), move_to(x,y,z), wait_for_moves()
    │                                     (note: GcodeGantry._send is one-line-per-ack;
    │                                      the showcase example uses raw serial to
    │                                      sidestep that until the lib is fixed)
    ├── ExperimentProfile             ──► load_experiment_profile(path) → typed dataclass with
    │                                     per-cycle volumes + optional gradient note
    ├── MotionProfile                 ──► select_profile(MOTION_PROFILE) → SLOW/MID/FAST
    │                                     bundled accel/jerk factor; as_marlin() emits the four
    │                                     bootstrap M-codes (M203/M201/M204/M205)
    └── cli_profile                   ──► build_volumes(default_count, unit_label) → shared
                                          env-var resolution for all showcases; routes
                                          PIPETTE_PROFILE / PIPETTE_VOLUME_UL to (volumes, banner)

dpette.DPetteDriver               ──► /dev/cu.usbserial-* (different device) @ 9600
                                       used by `preflight.py`; not exercised in the
                                       v0 showcase (plunger simulated via gantry Z).
```

Tests use fakes (`tests/conftest.py::FakeSerial`, `FakePipette`) to
cover both layers without hardware.

## Quality Thresholds

- `make validate` must be green before any commit:
  - `ruff format --check`, `ruff check` (rule sets E,F,I,UP,C90,W,N,B,A,SIM,TCH,S; mccabe max-complexity=10)
  - `mypy --strict src/`
  - `pytest -v -m "not hardware"`
- `make check_complexity` — complexipy max 15
- `make check_links` — lychee
- `make check_docs` — markdownlint
- New code must come with mocked-serial tests. Hardware tests are
  `@pytest.mark.hardware` and run only with physical hookup.

## Agent Quick Reference

| Need to…                                 | Do this                                                          |
|------------------------------------------|------------------------------------------------------------------|
| Add a new `PipetteBot` op                | Edit `src/pipettebot/bot.py`; add a `test_bot.py` case.          |
| Add a Marlin command                     | Edit `src/pipettebot/gantry.py::GcodeGantry`; mirror in tests.   |
| Add an experiment profile                | Drop a TOML under `examples/experiment_profiles/`; loader is `src/pipettebot/experiment_profile.py`. |
| Add a deck or calibration feature        | Don't yet — file under AGENT_REQUESTS.md. v0 stays raw `(x,y,z)`. |
| Send a raw dPette packet                 | Don't. Use `dpette.DPetteDriver` methods.                        |
| Modify Marlin firmware                   | Don't yet. Open an ADR in AGENT_REQUESTS.md.                     |
| Add a 3D-printable part                  | Add `build_*()` to a script under `tools/cad/<area>/`, register it in `tools/cad/parts.json`, run `make render_all`. See `.claude/rules/cad-script-conventions.md`. |
| Tune slicer settings                     | Edit a profile in `tools/slicer/profiles/*.ini` — never inline. See `.claude/rules/slicer-profile-source-of-truth.md`. |
| Mount something on the i3 print head     | Add to `tools/cad/i3/`, annotate the `build_*()` with `# Mass:`, keep total payload &lt; 300 g. See `.claude/rules/i3-carriage-payload-budget.md`. |
| Track a deferred feature                 | AGENT_REQUESTS.md.                                               |
| Record a gotcha you hit                  | AGENT_LEARNINGS.md.                                              |

## 3D Parts Pipeline

`tools/cad/` (build123d) generates STL+SVG; `tools/slicer/` (OrcaSlicer-first,
PrusaSlicer fallback) gates printability. Outputs land in top-level
`hardware/{stl,svg,gcode}/` (gitignored).

```text
tools/cad/parts.json                ── manifest: name, cad path, build_func, status
tools/cad/render.py                 ── manifest dispatcher (build123d only)
tools/cad/util/{export,stl_to_svg,theme_svgs}.py
tools/cad/labware/                  ── universal SBS parts (tip rack, plate holder)
tools/cad/dpette/                   ── cradles, tip ejector, ejection post
tools/cad/i3/                       ── print-head-mounted parts (carriage_dpette_mount stub)
tools/slicer/validate.py            ── headless slice, PASS/WARN/FAIL report
tools/slicer/profiles/i3mega_*.ini  ── shared between OrcaSlicer + PrusaSlicer
```

Workflow:

```bash
make setup_cad        # uv sync --extra cad (installs build123d)
make setup_slicer     # detect orca-slicer / OrcaSlicer / prusa-slicer
make render_parts     # build123d → hardware/stl/ + hardware/svg/
make check_prints     # slice each STL, scan for overhang/unsupported/bridge
make render_all       # render_parts + check_prints
```

Path-scoped rules apply only when working under `tools/cad/` or
`tools/slicer/`:

- `.claude/rules/cad-script-conventions.md`
- `.claude/rules/slicer-profile-source-of-truth.md`
- `.claude/rules/i3-carriage-payload-budget.md`
- `.claude/rules/cad-printability-gate.md`
