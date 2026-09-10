#!/usr/bin/env bats
# Exercises tools/deploy/bootstrap.sh's --dry-run path only. Real execution
# needs root + apt on a Pi; --dry-run must succeed without either so this
# suite runs unprivileged in CI / this sandbox.

SCRIPT="$BATS_TEST_DIRNAME/../../../tools/deploy/bootstrap.sh"

@test "bootstrap.sh --dry-run exits 0 without sudo/apt available" {
    run bash "$SCRIPT" --dry-run
    [ "$status" -eq 0 ]
}

@test "bootstrap.sh --dry-run reports dry_run=1 and does not execute apt-get" {
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"dry_run=1"* ]]
    [[ "$output" == *"+ sudo apt-get update"* ]]
    [[ "$output" == *"+ sudo apt-get install"* ]]
}

@test "bootstrap.sh --dry-run plans the dialout group membership" {
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"+ sudo usermod -aG dialout"* ]]
}

@test "bootstrap.sh --dry-run plans install/config dir creation" {
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"+ sudo mkdir -p"* ]]
    [[ "$output" == *"+ sudo chown -R"* ]]
}

@test "bootstrap.sh --dry-run creates the service user without --create-home" {
    # --create-home would populate /etc/skel into $INSTALL_DIR, which then
    # makes deploy.sh's `git clone` (needs an empty destination) fail on
    # every fresh Pi. Regression test for that bug.
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"useradd --system --user-group"* ]]
    [[ "$output" != *"--create-home"* ]]
}

@test "bootstrap.sh rejects an unknown flag" {
    run bash "$SCRIPT" --bogus
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown argument"* ]]
}
