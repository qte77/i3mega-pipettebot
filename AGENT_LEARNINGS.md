# Agent Learnings

Gotchas and non-obvious lessons we hit. Keep entries short, dated, and
actionable. Add a new entry every time you'd say "I wish someone had told me
that earlier."

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
