# Contributing

## Dev setup

Requires [`uv`](https://docs.astral.sh/uv/). Install once:
`curl -LsSf https://astral.sh/uv/install.sh | sh`.

```bash
git clone https://github.com/qte77/i3mega-pipettebot.git
cd i3mega-pipettebot
make init
make validate
```

`make init` runs `uv sync --extra dev`.

The Makefile is the single quality gate (`make validate` runs ruff format
check + lint, mypy strict, and pytest mocked). All recipes invoke tools via
`uv run`, so the project venv stays in sync without manual activation. No
pre-commit hooks; CI runs the same recipes.

## Branching and PRs

- Branch from `main`. Branch protection rejects merge commits — use **squash merges** only.
- Topical commits: one logical change per commit, descriptive message.
- Open a PR; ensure CI is green; squash-merge.

## Code conventions

- Python ≥3.11, mypy strict, ruff (rule sets in `pyproject.toml`).
- `src/pipettebot/` for library code. Four v0 modules (`gantry`, `bot`, `profiles`, `__init__`) — see AGENTS.md.
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
