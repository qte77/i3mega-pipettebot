#!/usr/bin/env bats
# End-to-end coverage for `make setup_prusa_presets` (issue #129).
#
# Runs against this environment's real, installed
# /usr/share/PrusaSlicer/profiles/PrusaResearch.ini bundle (confirmed
# present) but redirects the output via PRUSA_USER_DIR to an isolated
# bats temp dir, so it never touches a real user's
# ~/.config/PrusaSlicer/. (HOME itself is not overridden — this repo's
# sandbox blocks reassigning HOME outright — hence the explicit
# --user-dir seam on tools/slicer/resolve_presets.py.)

BUNDLE="/usr/share/PrusaSlicer/profiles/PrusaResearch.ini"

setup() {
    REPO_ROOT="$(cd "$(dirname "$BATS_TEST_FILENAME")/../.." && pwd)"
    FIXTURE_USER_DIR="$BATS_TEST_TMPDIR/PrusaSlicer"
}

@test "make setup_prusa_presets populates PRUSA_USER_DIR/{printer,print,filament}/" {
    if [ ! -f "$BUNDLE" ]; then
        skip "PrusaSlicer system bundle not installed in this environment"
    fi

    run make -C "$REPO_ROOT" setup_prusa_presets PRUSA_USER_DIR="$FIXTURE_USER_DIR"
    [ "$status" -eq 0 ]

    printer_ini="$FIXTURE_USER_DIR/printer/Original Prusa MK4 Input Shaper 0.4 nozzle.ini"
    print_ini="$FIXTURE_USER_DIR/print/0.20mm SPEED @MK4IS 0.4.ini"
    filament_ini="$FIXTURE_USER_DIR/filament/Prusa PLA.ini"

    [ -f "$printer_ini" ]
    [ -f "$print_ini" ]
    [ -f "$filament_ini" ]

    # The resolver pops `inherits` after flattening the chain — none of
    # the three written files should still carry it.
    run grep -q "^inherits" "$printer_ini"
    [ "$status" -eq 1 ]

    # A flattened MK4 IS printer preset should carry far more than a
    # handful of keys once its ancestor chain is walked.
    [ "$(wc -l < "$printer_ini")" -gt 20 ]
}
