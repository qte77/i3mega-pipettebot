# Contributing

## Dev setup

```bash
git clone https://github.com/Lambda-Biolab/i3mega-pipettebot.git
cd i3mega-pipettebot
pip install -e ".[dev]"
pre-commit install
make validate
```

## Branching and PRs

- Branch from `main`. Lambda-Biolab branch protection rejects merge commits — use **squash merges** only.
- Topical commits: one logical change per commit, descriptive message.
- Open a PR; ensure CI is green; squash-merge.

## Code conventions

- Python ≥3.11, mypy strict, ruff (rule sets in `pyproject.toml`).
- `src/pipettebot/` for library code. Three v0 modules only — see AGENTS.md.
- Tests use mocked serial fixtures from `tests/conftest.py`. New features need new tests.

## Hardware experiments

- Hardware-only tests get `@pytest.mark.hardware` and are skipped by default.
- Probe scripts go in `tools/` (create as needed); raw serial captures go in `captures/` (gitignored).
- Document non-obvious findings in [AGENT_LEARNINGS.md](AGENT_LEARNINGS.md).

## Backlog

Anything you'd like to add but isn't ready to ship: write it up in
[AGENT_REQUESTS.md](AGENT_REQUESTS.md) before opening an issue.
