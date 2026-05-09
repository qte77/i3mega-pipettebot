# Agent Learnings

Gotchas and non-obvious lessons we hit. Keep entries short, dated, and
actionable. Add a new entry every time you'd say "I wish someone had told me
that earlier."

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
