#!/usr/bin/env bats
# Coverage for `make slice` (issue #128). Mocks the PrusaSlicer binary —
# no real STL-to-gcode round-trip, matching how tools/slicer/validate.py's
# own tests stay pure-function-only (tests/tools/slicer/test_validate_cmd.py).
#
# A real (non-mocked) round-trip using this exact `--load`x3 invocation
# was verified manually against this environment's installed
# PrusaSlicer — see the module docstring in tools/slicer/slice.py.

setup() {
    REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    FIXTURE_AREA="_bats_fixture"
    FIXTURE_PART="widget_$$"
    STL_PATH="$REPO_ROOT/hardware/stl/$FIXTURE_AREA/$FIXTURE_PART.stl"
    BGCODE_PATH="$REPO_ROOT/hardware/bgcode/$FIXTURE_AREA/$FIXTURE_PART.bgcode"

    FIXTURE_PARTS_JSON="$BATS_TEST_TMPDIR/parts.json"
    FIXTURE_USER_DIR="$BATS_TEST_TMPDIR/PrusaSlicer"
    export FIXTURE_PART FIXTURE_AREA FIXTURE_PARTS_JSON
    python3 - <<'PYEOF'
import json
import os

json.dump(
    [{"name": os.environ["FIXTURE_PART"],
      "stl": f'{os.environ["FIXTURE_AREA"]}/{os.environ["FIXTURE_PART"]}.stl'}],
    open(os.environ["FIXTURE_PARTS_JSON"], "w"),
)
PYEOF

    mkdir -p "$(dirname "$STL_PATH")"
    printf 'fixture stl bytes' > "$STL_PATH"

    # Fixture presets so slice.py's pre-flight existence check passes —
    # mirrors what `make setup_prusa_presets` would have written.
    mkdir -p "$FIXTURE_USER_DIR/printer" "$FIXTURE_USER_DIR/print" "$FIXTURE_USER_DIR/filament"
    : > "$FIXTURE_USER_DIR/printer/Original Prusa MK4 Input Shaper 0.4 nozzle.ini"
    : > "$FIXTURE_USER_DIR/print/0.20mm SPEED @MK4IS 0.4.ini"
    : > "$FIXTURE_USER_DIR/filament/Prusa PLA.ini"

    export MOCK_LOG="$BATS_TEST_TMPDIR/prusa-slicer.args"
    MOCK_BIN="$BATS_TEST_TMPDIR/bin"
    mkdir -p "$MOCK_BIN"
    cat > "$MOCK_BIN/prusa-slicer" <<'EOF'
#!/usr/bin/env bash
# Mock PrusaSlicer: records its args and writes an empty bgcode at
# --output so slice.py's post-slice existence check passes.
echo "$@" >> "$MOCK_LOG"
out=""
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--output" ]; then
        out="$2"
    fi
    shift
done
[ -n "$out" ] && : > "$out"
EOF
    chmod +x "$MOCK_BIN/prusa-slicer"
    export PATH="$MOCK_BIN:$PATH"
}

teardown() {
    rm -rf "$REPO_ROOT/hardware/stl/$FIXTURE_AREA" "$REPO_ROOT/hardware/bgcode/$FIXTURE_AREA"
    rmdir "$REPO_ROOT/hardware/stl" "$REPO_ROOT/hardware/bgcode" "$REPO_ROOT/hardware" 2>/dev/null || true
}

@test "make slice PART=<fixture> writes hardware/bgcode/<area>/<part>.bgcode via the mocked slicer" {
    run make -C "$REPO_ROOT" slice PART="$FIXTURE_PART" PARTS_JSON="$FIXTURE_PARTS_JSON" PRUSA_USER_DIR="$FIXTURE_USER_DIR"
    [ "$status" -eq 0 ]
    [ -f "$BGCODE_PATH" ]

    run cat "$MOCK_LOG"
    [ "$status" -eq 0 ]
    [[ "$output" == *"--binary-gcode"* ]]
    [[ "$output" == *"--output $BGCODE_PATH"* ]]
}

@test "make slice with no PART fails with a usage message" {
    run make -C "$REPO_ROOT" slice
    [ "$status" -ne 0 ]
    [[ "$output" == *"Usage: make slice PART="* ]]
}

@test "make slice fails clearly when presets have not been set up yet (issue #129 dependency)" {
    EMPTY_USER_DIR="$BATS_TEST_TMPDIR/no-presets"
    run make -C "$REPO_ROOT" slice PART="$FIXTURE_PART" PARTS_JSON="$FIXTURE_PARTS_JSON" PRUSA_USER_DIR="$EMPTY_USER_DIR"
    [ "$status" -ne 0 ]
    [[ "$output" == *"make setup_prusa_presets"* ]]
    [ ! -f "$BGCODE_PATH" ]
}
