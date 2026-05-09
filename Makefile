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
	uv run ruff check src/ tests/ examples/ tools/
	uv run mypy src/

lint_fix:
	uv run ruff format src/ tests/ examples/ tools/
	uv run ruff check --fix src/ tests/ examples/ tools/

test:
	uv run pytest -v

validate:
	uv run ruff format --check src/ tests/ examples/ tools/
	uv run ruff check src/ tests/ examples/ tools/
	uv run mypy src/
	uv run pytest -v -m "not hardware"

quick_validate:
	uv run ruff check src/ tests/ examples/ tools/
	uv run mypy src/

check_complexity:
	uv run complexipy src/pipettebot/ --max-complexity-allowed 15

check_links:
	lychee --config .lychee.toml .

check_docs:
	markdownlint-cli2 "**/*.md" "#node_modules" "#.venv" "#.git"

render_parts:
	uv run --extra cad python tools/cad/render.py

check_prints:
	uv run python tools/slicer/validate.py --all

render_all: render_parts check_prints

all: lint test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache .ruff_cache dist build *.egg-info
