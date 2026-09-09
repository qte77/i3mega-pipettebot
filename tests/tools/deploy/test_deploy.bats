#!/usr/bin/env bats
# Exercises tools/deploy/deploy.sh's --dry-run path only. Real execution
# needs root + git/uv/systemd/udev on a Pi; --dry-run must succeed without
# any of them so this suite runs unprivileged in CI / this sandbox.

SCRIPT="$BATS_TEST_DIRNAME/../../../tools/deploy/deploy.sh"

@test "deploy.sh --dry-run exits 0 without sudo/git/systemctl available" {
    run bash "$SCRIPT" --dry-run
    [ "$status" -eq 0 ]
}

@test "deploy.sh --dry-run reports dry_run=1 and does not execute git" {
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"dry_run=1"* ]]
    [[ "$output" == *"+ sudo -u pipettebot git clone"* || "$output" == *"+ sudo -u pipettebot git -C"* ]]
}

@test "deploy.sh --dry-run plans the systemd unit and udev rule symlinks" {
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"+ sudo ln -sf"*"orchestrator.service"* ]]
    [[ "$output" == *"+ sudo ln -sf"*"99-pipettebot.rules"* ]]
}

@test "deploy.sh --dry-run never enables or starts the service" {
    run bash "$SCRIPT" --dry-run
    [[ "$output" != *"+ sudo systemctl enable"* ]]
    [[ "$output" != *"+ sudo systemctl start"* ]]
    [[ "$output" == *"NOT enabled/started"* ]]
}

@test "deploy.sh --dry-run installs deps via venv+pip, not uv" {
    # A uv-preferred path run through `sudo -u pipettebot` silently resolves
    # to "command not found" (sudo's secure_path drops a per-user
    # ~/.local/bin, and an operator's own uv install isn't readable by
    # another account's 700 $HOME) — regression test for that bug.
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"python3 -m venv .venv"* ]]
    [[ "$output" == *".venv/bin/pip install -e ."* ]]
    [[ "$output" != *" uv "* ]]
}

@test "deploy.sh --dry-run seeds a starter orchestrator.env when absent" {
    run bash "$SCRIPT" --dry-run
    [[ "$output" == *"+ sudo install -o pipettebot -g pipettebot -m 0640"*"orchestrator.env"* ]]
}

@test "deploy.sh rejects an unknown flag" {
    run bash "$SCRIPT" --bogus
    [ "$status" -ne 0 ]
    [[ "$output" == *"unknown argument"* ]]
}
