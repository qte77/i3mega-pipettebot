.PHONY: \
	init \
	setup_cad \
	setup_slicer \
	setup_diagramforge \
	setup_all \
	lint \
	lint_fix \
	test \
	validate \
	quick_validate \
	check_complexity \
	check_links \
	check_docs \
	render_parts \
	check_prints \
	render_all \
	all \
	clean \
	help
.DEFAULT_GOAL := help

.SILENT:
.ONESHELL:

# Pin diagramforge (TypeScript/Node draw.io bridge) to a known-good commit.
# diagramforge is a dev-time visualisation tool, not a runtime dep, so we
# soft-clone instead of using a real git submodule. Bump this SHA when you
# want a newer version.
DIAGRAMFORGE_SHA := d17ebf0e07063a4c8c61675f69faeeb88449bea9

# Prefer the pre-built venv to avoid `uv run` writing to ~/.cache/uv,
# which fails on read-only hosts (sandbox builds, sealed Pi images, some
# CI runners). `make init` / `make setup_cad` populate .venv first; the
# `uv run` fallback covers fresh clones where neither has run yet.
USE_VENV := $(shell test -x .venv/bin/python && echo yes || echo no)
ifeq ($(USE_VENV),yes)
  PY := .venv/bin/python
  RUFF := .venv/bin/ruff
  MYPY := .venv/bin/mypy
  PYTEST := .venv/bin/pytest
  PY_CAD := .venv/bin/python
else
  PY := uv run python
  RUFF := uv run ruff
  MYPY := uv run mypy
  PYTEST := uv run pytest
  PY_CAD := uv run --extra cad python
endif


# MARK: SETUP


init:  ## uv sync --extra dev (default dev environment)
	uv sync --extra dev

setup_cad:  ## uv sync --extra cad (build123d for CAD parts pipeline)
	uv sync --extra cad

setup_slicer:  ## Probe for OrcaSlicer (preferred) or PrusaSlicer (fallback)
	if command -v orca-slicer > /dev/null 2>&1; then
		echo "orca-slicer already installed: $$(orca-slicer --version 2>&1 | head -1)"
	elif command -v OrcaSlicer > /dev/null 2>&1; then
		echo "OrcaSlicer already installed: $$(OrcaSlicer --version 2>&1 | head -1)"
	elif command -v prusa-slicer > /dev/null 2>&1; then
		echo "prusa-slicer already installed (fallback): $$(prusa-slicer --version 2>&1 | head -1)"
	else
		echo "No slicer found. Install one of:"
		echo "  - OrcaSlicer (preferred): https://github.com/SoftFever/OrcaSlicer/releases"
		echo "  - PrusaSlicer (fallback): https://github.com/prusa3d/PrusaSlicer/releases"
		echo "Profiles in tools/slicer/profiles/ are .ini and work with both."
		exit 1
	fi

setup_diagramforge:  ## Clone diagramforge at $(DIAGRAMFORGE_SHA) if .gitmodules registers a URL
	if [ -e diagramforge/.git ]; then
		echo "diagramforge already present (HEAD: $$(git -C diagramforge rev-parse --short HEAD))"
	elif [ ! -f .gitmodules ]; then
		echo "WARN: .gitmodules missing — skipping"
	else
		url=$$(git config --file .gitmodules submodule.diagramforge.url 2>/dev/null)
		if [ -z "$$url" ]; then
			echo "WARN: submodule.diagramforge.url not set in .gitmodules — skipping"
		else
			echo "Cloning diagramforge from $$url at $(DIAGRAMFORGE_SHA) ..."
			git clone "$$url" diagramforge
			git -C diagramforge checkout --detach "$(DIAGRAMFORGE_SHA)"
		fi
	fi

setup_all: init setup_cad  ## init + setup_cad + best-effort slicer/diagramforge
	-$(MAKE) setup_slicer
	-$(MAKE) setup_diagramforge


# MARK: LINT


lint:  ## ruff check + mypy strict on src/tests/examples/tools
	$(RUFF) check src/ tests/ examples/ tools/
	$(MYPY) src/

lint_fix:  ## ruff format + ruff check --fix
	$(RUFF) format src/ tests/ examples/ tools/
	$(RUFF) check --fix src/ tests/ examples/ tools/


# MARK: TEST


test:  ## pytest -v (hardware tests excluded by pyproject)
	$(PYTEST) -v


# MARK: QUALITY


validate:  ## Full gate: ruff format --check + ruff check + mypy --strict + pytest -m "not hardware"
	$(RUFF) format --check src/ tests/ examples/ tools/
	$(RUFF) check src/ tests/ examples/ tools/
	$(MYPY) src/
	$(PYTEST) -v -m "not hardware"

quick_validate:  ## ruff check + mypy only (no tests)
	$(RUFF) check src/ tests/ examples/ tools/
	$(MYPY) src/

check_complexity:  ## complexipy src/pipettebot/ --max-complexity-allowed 15
	uv run complexipy src/pipettebot/ --max-complexity-allowed 15

check_links:  ## lychee link checker (.lychee.toml config)
	lychee --config .lychee.toml .

check_docs:  ## markdownlint-cli2 over all *.md (excludes node_modules/.venv/.git)
	markdownlint-cli2 "**/*.md" "#node_modules" "#.venv" "#.git"


# MARK: CAD


render_parts:  ## build123d → STL/SVG (manifest in tools/cad/parts.json)
	$(PY_CAD) tools/cad/render.py

check_prints:  ## Headless slice via tools/slicer/validate.py --all
	$(PY) tools/slicer/validate.py --all

render_all: render_parts check_prints  ## render_parts + check_prints (full CAD-to-slicer gate)


# MARK: META


all: lint test  ## lint + test

clean:  ## Remove caches and build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache .ruff_cache dist build *.egg-info


# MARK: HELP


help:  ## Show available recipes grouped by section
	@echo "Usage: make [recipe]"
	@echo ""
	@awk '/^# MARK:/ { \
		section = substr($$0, index($$0, ":")+2); \
		printf "\n\033[1m%s\033[0m\n", section \
	} \
	/^[a-zA-Z0-9_-]+:.*?##/ { \
		helpMessage = match($$0, /## (.*)/); \
		if (helpMessage) { \
			recipe = $$1; \
			sub(/:/, "", recipe); \
			printf "  \033[36m%-22s\033[0m %s\n", recipe, substr($$0, RSTART + 3, RLENGTH) \
		} \
	}' $(MAKEFILE_LIST)
