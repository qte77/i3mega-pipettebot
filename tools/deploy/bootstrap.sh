#!/usr/bin/env bash
# tools/deploy/bootstrap.sh — Pi 3 B+ system bootstrap for orchestrator.service.
#
# Installs the apt packages the orchestrator needs, creates a dedicated
# unprivileged service user (in the `dialout` group so it can open the
# /dev/i3mega and /dev/dpette serial symlinks — see 99-pipettebot.rules),
# and creates the install/config directories tools/deploy/deploy.sh and
# orchestrator.service expect.
#
# Idempotent: every step checks current state first, so re-running after a
# partial failure (or on an already-provisioned host) is safe.
#
# Usage:
#   sudo tools/deploy/bootstrap.sh [--dry-run]
#
# --dry-run prints every action that would be taken (prefixed `+`) without
# executing it — no apt-get, no useradd/usermod, no mkdir/chown. Safe to run
# without root or apt/sudo installed (this is how tests/tools/deploy/ exercises
# it in CI, where none of those are available).
#
# See docs/sbc-deployment.md for the wider Pi-as-host deployment picture and
# tools/setup_pi.sh for the older curl-pipe dev bring-up flow this
# complements (setup_pi.sh is for a manual dev bring-up session; this script
# + deploy.sh are the repeatable systemd-service deploy path, issue #126).

set -euo pipefail

SERVICE_USER="${PIPETTEBOT_USER:-pipettebot}"
INSTALL_DIR="${PIPETTEBOT_INSTALL_DIR:-/opt/pipettebot}"
CONFIG_DIR="${PIPETTEBOT_CONFIG_DIR:-/etc/pipettebot}"
APT_PACKAGES=(git python3-venv python3-pip curl)

DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *)
            echo "bootstrap.sh: unknown argument: $arg (only --dry-run is supported)" >&2
            exit 1
            ;;
    esac
done

log() { echo "[bootstrap] $*"; }

run() {
    log "+ $*"
    if [ "$DRY_RUN" -eq 0 ]; then
        "$@"
    fi
}

log "target: user=$SERVICE_USER install_dir=$INSTALL_DIR config_dir=$CONFIG_DIR dry_run=$DRY_RUN"

# 1. apt packages (idempotent: apt-get install is a no-op on already-installed pkgs)
run sudo apt-get update -qq
run sudo apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}"

# 2. service user (idempotent: skip useradd if it already exists; usermod -aG
#    is itself idempotent so it's safe to repeat every run)
if getent passwd "$SERVICE_USER" > /dev/null 2>&1; then
    log "user $SERVICE_USER already exists — skipping useradd"
else
    # No --create-home: with --home-dir this only records the path in
    # passwd, it does NOT populate it from /etc/skel. Step 3 below creates
    # it empty, which deploy.sh's `git clone` (a fresh checkout requires an
    # empty destination) depends on. --user-group makes a dedicated
    # pipettebot:pipettebot group explicit rather than relying on the
    # distro's USERGROUPS_ENAB default (the unit's Group=pipettebot needs it
    # to exist either way).
    run sudo useradd --system --user-group --shell /usr/sbin/nologin \
        --home-dir "$INSTALL_DIR" "$SERVICE_USER"
fi
run sudo usermod -aG dialout "$SERVICE_USER"

# 3. dirs (idempotent: mkdir -p / chown are no-ops on an already-correct tree)
run sudo mkdir -p "$INSTALL_DIR" "$CONFIG_DIR"
run sudo chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

log "bootstrap complete. Next: tools/deploy/deploy.sh"
