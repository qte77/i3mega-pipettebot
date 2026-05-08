# AGENTS.md — i3mega-pipettebot

Single source of truth for agents working in this repo. `CLAUDE.md` and
`GEMINI.md` redirect here.

## Claude Code Infrastructure

- Doc hierarchy: AGENTS.md → AGENT_LEARNINGS.md, AGENT_REQUESTS.md, CONTRIBUTING.md, CHANGELOG.md
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
5. **Topical commits with squash-merge.** Lambda-Biolab branch protection
   rejects merge commits. Use `git merge --squash` or PR squash.

## Decision Framework

| Question                                        | Answer for v0                                                    |
|-------------------------------------------------|------------------------------------------------------------------|
| Where does new code go?                         | `src/pipettebot/`. Three modules only: `gantry`, `bot`, `__init__`. |
| Where does deck geometry live?                  | Deferred. Caller passes raw `(x, y, z)` in v0.                   |
| How is dpette imported?                         | Git dep, pinned to a commit SHA before v0.0.1 tag.               |
| Where do hardware experiments go?               | `tools/` (not yet created), with logs to `captures/`.            |
| What goes in AGENT_REQUESTS.md?                 | Anything deferred — features, ADRs, hardware photos, firmware tracks. |

## Architecture Overview

```text
examples/showcase_v0_pipette_sim.py
        │
        ▼
raw pyserial @ 250000 baud   ──► /dev/cu.usbserial-*  Marlin (Anycubic stock / AI3M)
        │
        └─ optional tee       ──► .gcode file for SD replay

src/pipettebot/                        (library, used by examples & tests)
    ├── PipetteBot                    ──► aspirate_at(x,y,z,vol), dispense_at(x,y,z), home()
    └── GcodeGantry                   ──► home(), move_to(x,y,z), wait_for_moves()
                                          (note: GcodeGantry._send is one-line-per-ack;
                                           the showcase example uses raw serial to
                                           sidestep that until the lib is fixed)

dpette.DPetteDriver               ──► /dev/cu.usbserial-* (different device) @ 9600
                                       used by `preflight.py`; not exercised in the
                                       v0 showcase (plunger simulated via gantry Z).
```

Tests use fakes (`tests/conftest.py::FakeSerial`, `FakePipette`) to
cover both layers without hardware.

## Quality Thresholds

- `make validate` must be green before any commit:
  - `ruff format --check`, `ruff check` (rule sets E,F,I,UP,C90,W,N,B,A,SIM,TCH)
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
| Add a deck or calibration feature        | Don't yet — file under AGENT_REQUESTS.md. v0 stays raw `(x,y,z)`. |
| Send a raw dPette packet                 | Don't. Use `dpette.DPetteDriver` methods.                        |
| Modify Marlin firmware                   | Don't yet. Open an ADR in AGENT_REQUESTS.md.                     |
| Track a deferred feature                 | AGENT_REQUESTS.md.                                               |
| Record a gotcha you hit                  | AGENT_LEARNINGS.md.                                              |
