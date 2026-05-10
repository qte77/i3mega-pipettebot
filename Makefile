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
	clean

.SILENT:
.ONESHELL:

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

init:
	uv sync --extra dev

setup_cad:
	uv sync --extra cad

setup_slicer:
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

setup_diagramforge:
	if [ -e diagramforge/.git ]; then
		echo "diagramforge already present"
	elif [ ! -f .gitmodules ]; then
		echo "WARN: .gitmodules missing — skipping"
	else
		url=$$(git config --file .gitmodules submodule.diagramforge.url 2>/dev/null)
		if [ -z "$$url" ]; then
			echo "WARN: submodule.diagramforge.url not set in .gitmodules — skipping"
		else
			echo "Cloning diagramforge from $$url ..."
			git clone "$$url" diagramforge
		fi
	fi

setup_all: init setup_cad
	-$(MAKE) setup_slicer
	-$(MAKE) setup_diagramforge

lint:
	$(RUFF) check src/ tests/ examples/ tools/
	$(MYPY) src/

lint_fix:
	$(RUFF) format src/ tests/ examples/ tools/
	$(RUFF) check --fix src/ tests/ examples/ tools/

test:
	$(PYTEST) -v

validate:
	$(RUFF) format --check src/ tests/ examples/ tools/
	$(RUFF) check src/ tests/ examples/ tools/
	$(MYPY) src/
	$(PYTEST) -v -m "not hardware"

quick_validate:
	$(RUFF) check src/ tests/ examples/ tools/
	$(MYPY) src/

check_complexity:
	uv run complexipy src/pipettebot/ --max-complexity-allowed 15

check_links:
	lychee --config .lychee.toml .

check_docs:
	markdownlint-cli2 "**/*.md" "#node_modules" "#.venv" "#.git"

render_parts:
	$(PY_CAD) tools/cad/render.py

check_prints:
	$(PY) tools/slicer/validate.py --all

render_all: render_parts check_prints

all: lint test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache .ruff_cache dist build *.egg-info
