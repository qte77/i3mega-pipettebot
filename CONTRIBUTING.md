# Contributing

## Dev setup

Requires [`uv`](https://docs.astral.sh/uv/). Install once:
`curl -LsSf https://astral.sh/uv/install.sh | sh`.

```bash
git clone https://github.com/qte77/i3mega-pipettebot.git
cd i3mega-pipettebot
make setup_dev
make validate
```

`make setup_dev` runs `uv sync --inexact --extra dev`. Other entry points:
`make setup_prod` for runtime-only (`uv sync --inexact`); `make setup_uv`
to bootstrap uv itself; `make setup_all` for dev + cad + best-effort
slicer/diagramforge. `make help` lists everything.

The `--inexact` flag makes the setup recipes **additive** — running
`setup_dev` after `setup_cad` keeps build123d installed (and vice
versa). Without it, `uv sync` is exact and uninstalls anything not in
the requested extras.

The Makefile is the single quality gate (`make validate` runs ruff format
check + lint, mypy strict, and pytest mocked). Each recipe prefers the
local `.venv/bin/<tool>` binary, falling back to `uv run` if the venv
is missing. No pre-commit hooks; CI runs the same recipes.

## Branching and PRs

- Branch from `main`. Branch protection rejects merge commits — use **squash merges** only.
- Topical commits: one logical change per commit, descriptive message.
- Open a PR; ensure CI is green; squash-merge.

## Code conventions

- Python ≥3.11, mypy strict, ruff (rule sets in `pyproject.toml`).
- `src/pipettebot/` for library code. Seven v0 modules (`gantry`, `bot`, `devices`, `experiment_profile`, `motion_profile`, `cli_profile`, `__init__`) — see AGENTS.md.
- Tests use mocked serial fixtures from `tests/conftest.py`. New features need new tests.

## Hardware experiments

- Hardware-only tests get `@pytest.mark.hardware` and are skipped by default.
- Probe scripts go in `tools/` (create as needed); raw serial captures go in `captures/` (gitignored).
- Document non-obvious findings in [AGENT_LEARNINGS.md](AGENT_LEARNINGS.md).

## Deferred work

Actionable items belong in [open issues](https://github.com/qte77/i3mega-pipettebot/issues).
[AGENT_REQUESTS.md](AGENT_REQUESTS.md) is a short-term communication
channel for agents and humans (hand-off notes, requests, decisions
that need input) — not a backlog or task tracker.
