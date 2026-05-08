# Agent Learnings

Gotchas and non-obvious lessons we hit. Keep entries short, dated, and
actionable. Add a new entry every time you'd say "I wish someone had told me
that earlier."

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
