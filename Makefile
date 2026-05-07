.PHONY: \
	init \
	lint \
	lint_fix \
	test \
	validate \
	quick_validate \
	check_complexity \
	check_links \
	check_docs \
	all \
	clean

.SILENT:
.ONESHELL:

init:
	uv sync --extra dev

lint:
	uv run ruff check src/ tests/ examples/
	uv run mypy src/

lint_fix:
	uv run ruff format src/ tests/ examples/
	uv run ruff check --fix src/ tests/ examples/

test:
	uv run pytest -v

validate:
	uv run ruff format --check src/ tests/ examples/
	uv run ruff check src/ tests/ examples/
	uv run mypy src/
	uv run pytest -v -m "not hardware"

quick_validate:
	uv run ruff check src/ tests/ examples/
	uv run mypy src/

check_complexity:
	uv run complexipy src/pipettebot/ --max-complexity-allowed 15

check_links:
	lychee --config .lychee.toml .

check_docs:
	markdownlint-cli2 "**/*.md" "#node_modules" "#.venv" "#.git"

all: lint test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache .ruff_cache dist build *.egg-info
