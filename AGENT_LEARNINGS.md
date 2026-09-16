# Agent Learnings

Gotchas and non-obvious lessons we hit. Keep entries short, dated, and
actionable. Add a new entry every time you'd say "I wish someone had told me
that earlier."

## 2026-09-16 — Two carriage-mount designs coexist on purpose: don't "fix" the duplication

`tools/cad/i3/carriage_dpette_mount.py` (production, M3-bolted upper clamp)
and `tools/cad/i3/carriage_dpette_mount_frictionfit.py` (testing, glue/
friction-fit upper clamp) both build a main+cap+lbracket mount for the same
physical joint. This is deliberate, not accidental duplication — PR #78's
branch had diverged 75 commits from `main` and reached a fundamentally
different design (different bore diameter, axis separation, lower-clamp
geometry with J-hooks, hole placement) through real physical dry-fit
iteration, while `main`'s bolted design shipped independently in the
meantime. The two designs are NOT interchangeable variants of shared
constants — they need different pipette bore/separation measurements, so
the friction-fit module keeps its own local `FRICTIONFIT_*` constants
rather than sharing `measurements.py`'s `UPPER_CLAMP_BORE_D_MM` /
`UPPER_TO_LOWER_SEPARATION_MM` (which the production bolted design is
built and validated against).

Issue #75 (filed from the same branch) explains *why* friction-fit was
abandoned: the bore size never converged after 5 dry-fit rounds, and
glue/friction isn't robust under vibration or serviceable. #75 asks for
M3 bolts back — which matches `carriage_dpette_mount.py`'s production
constants exactly — but its bore re-measurement (Ø27 -> Ø24.5 mm) was
never carried over. **#75 is still open and only half-resolved**: don't
close it without either re-measuring the bolted design's bore on real
hardware or explicitly deciding Ø27 mm is correct after all.

**Rule**: before touching either file, check which one you mean to change.
`parts.json`'s `"status": "testing"` on the frictionfit entries is the only
marker distinguishing "the one being physically validated" from "the
production target" — don't delete the testing variant as "dead code," and
don't silently merge its constants into the shared production ones without
physical dry-fit confirmation on the bolted design.

## 2026-09-09 — `systemd-analyze verify` always fails pre-deploy on a unit whose ExecStart lives in the deploy target

Hit writing `tools/deploy/orchestrator.service` (issue #126). Its
`ExecStart=` points at `/opt/pipettebot/.venv/bin/python`, a path that only
exists after `tools/deploy/deploy.sh` has actually run on the target host.
`systemd-analyze verify` checks that the `ExecStart=` binary exists and is
executable, so it reports `Command ... is not executable: No such file or
directory` in every environment that hasn't deployed yet — CI, a dev
container, a fresh clone before first deploy. This is expected, not a unit
bug.

**Diagnostic**: to confirm the REST of a unit file is valid despite this,
copy it to a scratch path and swap `ExecStart=` for a binary that already
exists (e.g. `/bin/true`), then `systemd-analyze verify` the scratch copy —
a clean run there means only the not-yet-deployed path is at fault.

**Also found in the same pass**: this sandbox's `udevadm` binary is
genuinely absent by default (containers don't run a live udev daemon), not
merely lacking a mock sysfs tree. `apt-get install udev` does provide a
working standalone binary — `udevadm verify <rules-file>` syntax-checks a
rules file with no daemon needed, and `udevadm test <sysfs-devpath>`
parses the full installed ruleset (including a temporarily-copied custom
rules file) against a real `/sys/class/tty/*` path — but neither exercises
an actual VID:PID match without real USB-serial hardware attached.
`Makefile`'s `check_deploy` target treats both `systemd-analyze verify` and
`udevadm` as best-effort/non-fatal for exactly this reason.

## 2026-09-09 — floating `@main` git dependency + no `uv.lock` breaks CI on every upstream bump

`pyproject.toml`'s `orchestrator` extra pinned `so101-biolab-automation` to
`@main` (a floating ref) instead of a commit SHA. `uv.lock` is deliberately
gitignored (library project — see the `.gitignore` comment), so every CI run
re-resolves dependencies from scratch. When so101's `main` bumped its
`fastapi` floor past `[tool.uv] exclude-newer`, then bumped `numpy` too days
later, `uv sync` failed universally on `main` for ~2 months — even the 3.11
job, because uv resolves one universal lockfile across all `requires-python`
markers, so an unsatisfiable split for `python_full_version >= '3.12'` fails
the whole sync regardless of which interpreter actually runs.

**Solution**: pin `so101-biolab-automation` to a commit SHA (mirrors the
`dpette` pin two lines above it in the same file) instead of `@main`, and
bump `[tool.uv] exclude-newer` forward to cover that commit's own floor.
`exclude-newer-package` per-dependency overrides are whack-a-mole here — the
next transitive dep so101 bumps just breaks a different package.

**Still open**: the no-`uv.lock` policy is what let this recur silently;
committing it would freeze CI reproducibility without affecting the
published wheel (uv.lock is never included in sdists/wheels), but that
reverses a deliberate decision — flagged for the repo owner, not changed
here.

## 2026-05-17 — Marlin Y vs CAD top-view Y point opposite directions

Hit in `tools/cad/labware/deck_plate.py::build_deck_plate_assembly`.
Marlin frame is `+Y` FRONT (toward operator), standard CAD top-down is
`+Y` BACK (away from viewer) — an assembly built from raw Marlin coords
looks mirrored front-to-back in FreeCAD / PrusaSlicer / draw.io.

Promoted to `.claude/rules/cad-script-conventions.md` ("Assembly STLs:
mirror Y after Marlin-frame translation"). Rule: any `build_*_assembly()`
applies `mirror(translated, about=Plane.XZ)` after the Marlin-frame
translation. Per-half / printable parts stay in Marlin frame.

## 2026-05-09 — pyserial 3.5 cannot open 250000 baud on Linux Python builds without `termios.B250000`

Symptom: `serial.Serial(port, 250000, timeout=...)` raises
`termios.error: (22, 'Invalid argument')` from `_reconfigure_port`'s
`tcsetattr` call. Hit in `tools/preflight.py` (#30) and
`examples/showcase_v0_i3_pipette_sim.py` (same root cause, separate script;
renamed from `showcase_v0_pipette_sim.py` in PR #157).

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
