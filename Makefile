.PHONY: \
	setup_uv \
	setup_prod \
	setup_dev \
	setup_cad \
	setup_slicer \
	setup_freecad \
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

# Per-tool dispatch: prefer the binary in .venv/bin if it exists, else fall
# back to `uv run`. `uv run` lazily resolves and installs into .venv, so
# `make test` works even if you only ran `uv sync` (no `--extra dev`). On
# read-only hosts that block ~/.cache/uv writes, set UV_CACHE_DIR to a
# writable path (e.g. `UV_CACHE_DIR=$$TMPDIR/uv-cache make test`).
RUFF   := $(shell test -x .venv/bin/ruff   && echo .venv/bin/ruff   || echo "uv run ruff")
MYPY   := $(shell test -x .venv/bin/mypy   && echo .venv/bin/mypy   || echo "uv run mypy")
PYTEST := $(shell test -x .venv/bin/pytest && echo .venv/bin/pytest || echo "uv run pytest")
PY     := $(shell test -x .venv/bin/python && echo .venv/bin/python || echo "uv run python")
PY_CAD := $(shell test -x .venv/bin/python && echo .venv/bin/python || echo "uv run --extra cad python")

# Quiet mode (default: quiet; set VERBOSE=1 for full tool output).
# Each recipe echoes a `--- <name>` header so the active step stays visible.
VERBOSE ?=
ifndef VERBOSE
  RUFF_QUIET   := --quiet
  PYTEST_QUIET := -q --tb=short --no-header
  CPLX_QUIET   := -q
endif


# MARK: SETUP


# All setup_{prod,dev,cad} recipes pass `--inexact` to `uv sync`. By
# default `uv sync` is exact — it uninstalls everything not in the
# requested extras — so without this flag `make setup_dev` would wipe
# out `build123d` from a prior `make setup_cad`, and vice versa. With
# `--inexact` the recipes are additive: any chain ends with the union
# of installed extras, matching the `setup_all` recipe's intent.
# See https://docs.astral.sh/uv/reference/cli/#uv-sync for details.

setup_uv:  ## Install uv (Python package manager) if missing
	if command -v uv > /dev/null 2>&1; then
		echo "uv already installed: $$(uv --version)"
	else
		echo "Installing uv ..."
		curl -LsSf https://astral.sh/uv/install.sh | sh
		echo "uv installed. You may need to restart your shell or 'source ~/.bashrc'."
	fi

setup_prod:  ## uv sync (runtime deps only — pyserial + dpette)
	uv sync --inexact

setup_dev:  ## uv sync --extra dev (runtime + ruff/mypy/pytest/complexipy/hypothesis)
	uv sync --inexact --extra dev

setup_cad:  ## uv sync --extra cad (build123d for CAD parts pipeline)
	uv sync --inexact --extra cad

setup_slicer:  ## Probe for OrcaSlicer (preferred) or PrusaSlicer (fallback)
	if command -v orca-slicer > /dev/null 2>&1; then
		echo "orca-slicer already installed: $$(orca-slicer --version 2>&1 | head -1)"
	elif command -v OrcaSlicer > /dev/null 2>&1; then
		echo "OrcaSlicer already installed: $$(OrcaSlicer --version 2>&1 | head -1)"
	elif command -v prusa-slicer > /dev/null 2>&1; then
		# PrusaSlicer has no --version flag; the banner line lives in --help output.
		echo "prusa-slicer already installed (fallback): $$(prusa-slicer --help 2>&1 | grep -m1 '^PrusaSlicer-' || echo 'version unknown')"
	else
		echo "No slicer found. Install one of:"
		echo "  - OrcaSlicer (preferred): https://github.com/SoftFever/OrcaSlicer/releases"
		echo "  - PrusaSlicer (fallback): https://github.com/prusa3d/PrusaSlicer/releases"
		echo "Profiles in tools/slicer/profiles/ are .ini and work with both."
		exit 1
	fi

setup_freecad:  ## Probe for FreeCAD (optional — inspect generated STEP files)
	if command -v freecad > /dev/null 2>&1; then
		echo "freecad already installed: $$(freecad --version 2>&1 | head -1)"
	elif command -v FreeCAD > /dev/null 2>&1; then
		echo "FreeCAD already installed: $$(FreeCAD --version 2>&1 | head -1)"
	else
		echo "FreeCAD not found. Optional — used to inspect STEP files in hardware/step/."
		echo ""
		echo "Official downloads (per https://www.freecad.org/downloads.php):"
		echo "  Linux  AppImage:  github.com/FreeCAD/FreeCAD/releases  (x86_64 / aarch64)"
		echo "  macOS  DMG:       github.com/FreeCAD/FreeCAD/releases  (arm64 / x86_64)"
		echo ""
		echo "Distro packages (typically available, not endorsed by FreeCAD upstream):"
		echo "  Fedora:   sudo dnf install freecad"
		echo "  Debian:   sudo apt install freecad"
		echo "  Flatpak:  flatpak install flathub org.freecad.FreeCAD"
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

setup_all: setup_dev setup_cad  ## setup_dev + setup_cad + best-effort slicer/freecad/diagramforge
	# -s on sub-make suppresses both recipe echo and the auto "Entering directory" chatter
	-$(MAKE) -s setup_slicer
	-$(MAKE) -s setup_freecad
	-$(MAKE) -s setup_diagramforge


# MARK: LINT


lint:  ## ruff check + mypy strict on src/tests/examples/tools (VERBOSE=1 for full output)
	echo "--- lint$(if $(RUFF_QUIET), [quiet])"
	$(RUFF) check $(RUFF_QUIET) src/ tests/ examples/ tools/
	$(MYPY) src/

lint_fix:  ## ruff format + ruff check --fix (VERBOSE=1 for full output)
	echo "--- lint_fix$(if $(RUFF_QUIET), [quiet])"
	$(RUFF) format $(RUFF_QUIET) src/ tests/ examples/ tools/
	$(RUFF) check $(RUFF_QUIET) --fix src/ tests/ examples/ tools/


# MARK: TEST


test:  ## pytest (hardware tests excluded by pyproject; VERBOSE=1 for full output)
	echo "--- test$(if $(PYTEST_QUIET), [quiet])"
	$(PYTEST) $(if $(PYTEST_QUIET),$(PYTEST_QUIET),-v)


# MARK: QUALITY


validate:  ## Full gate: ruff format --check + ruff check + mypy --strict + pytest (VERBOSE=1 for full output)
	echo "--- validate$(if $(RUFF_QUIET), [quiet])"
	$(RUFF) format $(RUFF_QUIET) --check src/ tests/ examples/ tools/
	$(RUFF) check $(RUFF_QUIET) src/ tests/ examples/ tools/
	$(MYPY) src/
	$(PYTEST) $(if $(PYTEST_QUIET),$(PYTEST_QUIET),-v) -m "not hardware"

quick_validate:  ## ruff check + mypy only (no tests; VERBOSE=1 for full output)
	echo "--- quick_validate$(if $(RUFF_QUIET), [quiet])"
	$(RUFF) check $(RUFF_QUIET) src/ tests/ examples/ tools/
	$(MYPY) src/

check_complexity:  ## complexipy src/pipettebot/ --max-complexity-allowed 15 (VERBOSE=1 for full output)
	echo "--- check_complexity$(if $(CPLX_QUIET), [quiet])"
	uv run complexipy $(CPLX_QUIET) src/pipettebot/ --max-complexity-allowed 15

check_links:  ## lychee link checker (.lychee.toml config)
	lychee --config .lychee.toml .

check_docs:  ## markdownlint-cli2 over all *.md (excludes node_modules/.venv/.git/vendored clones)
	markdownlint-cli2 "**/*.md" "#node_modules" "#.venv" "#.git" "#diagramforge" "#hardware" "#captures"


# MARK: CAD


render_parts:  ## build123d → STL/STEP/SVG (manifest in tools/cad/parts.json)
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
