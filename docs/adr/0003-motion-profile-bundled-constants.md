# ADR 0003: Motion profile factors as bundled Python constants + `MOTION_PROFILE` env selector

- **Status:** Accepted
- **Date:** 2026-05-17
- **Scope:** [qte77/i3mega-pipettebot](https://github.com/qte77/i3mega-pipettebot) only

## Context

PR #113 shipped a unified XYZ liquid-handling motion profile across all six
gantry-using `examples/*.py` scripts in their bootstraps, with the four
M-codes (`M203` / `M201` / `M204` / `M205`) hardcoded inline in each script.

Hardware DRY-RUN feedback surfaced two issues:

1. **The Z accel of 80 mm/s² was over-cautious.** The user requested a
   leadscrew-friendly floor of 200 mm/s² and a way to dial higher (`fast`)
   or lower (`slow`) without editing code.
2. **Hardcoded numbers in six places** is a duplication smell. Tuning the
   profile meant editing six files in lock-step, with no runtime knob and
   no single source of truth.

A clean solution is to extract the motion profile into a small library
module + provide an env-var-selected named factor (slow / mid / fast).

## Decision

Bundle three named motion profiles as Python constants in
`src/pipettebot/motion_profile.py`:

```python
SLOW = MotionProfile("slow", accel_x=300,  accel_y=400,  accel_z=100,
                              accel_default=300,  jerk_x=1.5, jerk_y=2.5, jerk_z=0.1)
MID  = MotionProfile("mid",  accel_x=600,  accel_y=800,  accel_z=200,
                              accel_default=600,  jerk_x=3,   jerk_y=5,   jerk_z=0.2)
FAST = MotionProfile("fast", accel_x=1200, accel_y=1600, accel_z=400,
                              accel_default=1200, jerk_x=6,   jerk_y=10,  jerk_z=0.4)
```

SLOW / MID / FAST scale by an exact factor of 2x: SLOW x2 = MID,
MID x2 = FAST. MID is the operator-validated anchor. Earlier values
had non-uniform spacing (FAST = 1.67x MID on accel_x) — retuned for
predictable behavior when operators tune per-leg feedrates inside
these caps.

Feedrate caps (`M203`) are shared across all profiles — `X=500 Y=500 Z=20` —
since they reflect the leadscrew mechanical limit on Z and a reasonable
XY cruise speed, not a tuning choice.

Examples select at runtime via the `MOTION_PROFILE` env var:

| `MOTION_PROFILE` value | Behavior |
|---|---|
| unset | Load `mid` (default; preserves "every script lands in a known state") |
| `slow` / `mid` / `fast` | Load that bundled profile |
| empty `""` or `off` | Skip motion-profile install entirely (Marlin keeps RAM/EEPROM state) |

Loader: `select_profile(env_value: str | None) -> MotionProfile | None`,
re-exported from `pipettebot` for public API discoverability.

### Naming alignment

Existing pipetting-profile surface renamed in lockstep so the two
"profile" concepts are unambiguous:

- `src/pipettebot/profiles.py` → `src/pipettebot/experiment_profile.py`
- `examples/profiles/` → `examples/experiment_profiles/`
- `load_profile()` → `load_experiment_profile()`
- `ExperimentProfile` dataclass unchanged

Both modules now follow the `*_profile.py` convention.

### Alternatives considered

| Alternative | Why rejected |
|---|---|
| **TOML files in `examples/experiment_profiles/motion/*.toml`** | Would have `src/` pointing into `examples/` for runtime data, breaking the "library self-contained" invariant. Pipetting profiles are different — they're user-authored experiment data and naturally live in `examples/`. |
| **Inline constants per example script (status quo, just typed)** | Duplication smell — six-place edits per tuning change. |
| **Single `MotionProfile` instance + per-axis env overrides** (e.g. `MOTION_PROFILE_Z_ACCEL=300`) | Flexible but YAGNI — named factors are easier to reason about and discuss in PR review. Numeric overrides can be added later if needed. |
| **Persist selected profile to EEPROM via `M500`** | Couples Marlin state to script invocation order; bypasses the script-side env-var pattern. Out of scope for v0. |
| **Custom profile via arbitrary `MOTION_PROFILE=path/to/custom.toml`** | Same self-containment objection as the TOML option. v0 audience is small; custom profiles can be added as Python constants if the named set is insufficient. |

## Consequences

### Pros

- **Single source of truth** for motion tuning. Changes land in one
  file, not six.
- **Runtime selection without code edits.** `MOTION_PROFILE=fast` /
  `MOTION_PROFILE=slow` dials between factors per invocation.
- **Self-contained library.** `src/pipettebot/` carries the motion data
  as code — no inter-directory pointer to `examples/`.
- **Symmetric naming convention.** `experiment_profile.py` and
  `motion_profile.py` sit side-by-side under the same convention.
- **Opt-out is explicit.** `MOTION_PROFILE=off` (or empty) leaves
  Marlin RAM/EEPROM untouched — respects users who hand-tuned via
  `M500`.

### Cons

- **Custom motion profiles require a code change.** Acceptable for v0
  given the small audience; revisit if external contributors start
  needing arbitrary profiles.
- **The named-factor set is opinionated.** "slow / mid / fast" doesn't
  capture every dimension someone might want to tune (e.g. wet vs.
  dry-tip XY feed — that's a Tier 3 future concern).

### Neutral

- **One new module + one new test file in `src/` and `tests/`.** Small
  addition to the public API surface (`MotionProfile`, `select_profile`).
- **Rename of pipetting-profile surface** propagates to README,
  CHANGELOG, AGENTS, CONTRIBUTING path references — mechanical but
  touches several files. Landed as a separate commit before the
  motion_profile feature to keep history reviewable.

## Out of scope

- **Tier 2 per-move techniques** (Z touchdown/breakaway splits, XY
  settling dwells, droplet-stabilization dwells) — tracked as a
  follow-up; first applied selectively to
  `showcase_v0_full_pipettebot_rows.py` in this same PR as
  per-dive feedrate slowdowns, but not yet generalized into the
  `MotionProfile` dataclass.
- **Tier 3 wet vs. dry XY feed split** — deferred to a follow-up PR.
- **Motion profile visualization tool** (`tools/motion_profile_plot.py`)
  — tracked in a separate GitHub issue; renders the active profile as
  kinematics + 3-view path SVGs for design-review.
- **Real hardware kinematics capture** (M114-polled traces or external
  accelerometer) — deep-scope follow-up that compares simulated vs.
  measured trajectory; same tracking issue as the plot tool.

## References

- [PR #113](https://github.com/qte77/i3mega-pipettebot/pull/113) — the
  unified XYZ motion profile + the refactor into this module.
- `src/pipettebot/experiment_profile.py` — the existing
  pipetting-profile loader, kept structurally separate because the two
  profile types serve different audiences (user-authored experiment
  data vs. bundled hardware tuning).
- [ADR 0001](./0001-repo-structure-alignment.md) — sets the `src/<pkg>/`
  layout convention this ADR extends.
