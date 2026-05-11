#!/usr/bin/env bash
# tools/setup_pi.sh — Pi-as-host provisioning helper for i3mega-pipettebot.
#
# Runs ON the Pi after first SSH. Targets the Pi 1 Model B+ (ARMv6 armhf)
# but the arch check accepts armv7l / aarch64 too.
#
# One-shot bootstrap: system deps → uv (with system-pip fallback for
# arches uv doesn't ship for) → repo clone → dep sync → mocked test gate
# → port discovery → stable /dev/serial/by-id/... env file at
# config/pipettebot.env.
#
# Idempotent: safe to re-run after a partial failure.

set -euo pipefail

REPO_URL="https://github.com/Lambda-Biolab/i3mega-pipettebot.git"
REPO_DIR="${REPO_DIR:-$HOME/i3mega-pipettebot}"
ENV_FILE="config.local/pipettebot.env"

log() { echo "[setup_pi] $*"; }
die() { echo "[setup_pi] ERROR: $*" >&2; exit 1; }

# 1. arch + OS sanity
OS=$(uname -s)
ARCH=$(uname -m)
[ "$OS" = "Linux" ] || die "this script targets Linux. Got $OS."
case "$ARCH" in
    armv6l|armv7l|aarch64|arm64) log "arch=$ARCH os=$OS — supported" ;;
    *) log "WARN: arch=$ARCH is untested. Proceeding anyway." ;;
esac

# 2. system deps
log "installing system deps (git, python3-venv, pip, curl)"
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
    git python3-venv python3-pip curl

# 3. uv install (with ARMv6 fallback)
USE_UV=1
if ! command -v uv >/dev/null 2>&1; then
    log "installing uv"
    if curl -LsSf https://astral.sh/uv/install.sh | sh; then
        export PATH="$HOME/.local/bin:$PATH"
    fi
    if ! command -v uv >/dev/null 2>&1; then
        log "uv unavailable on $ARCH; falling back to system Python"
        USE_UV=0
    fi
fi

# 4. repo clone (idempotent)
if [ ! -d "$REPO_DIR/.git" ]; then
    log "cloning $REPO_URL → $REPO_DIR"
    git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"

# 5. dep sync (5-15 min on a Pi 1 B+)
log "syncing dependencies"
START=$(date +%s)
if [ "$USE_UV" = "1" ]; then
    make init
else
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -e '.[dev]'
fi
log "dep sync took $(( $(date +%s) - START ))s"

# 6. mocked test gate
log "running mocked test suite"
make test

# 7. port discovery + by-id rewrite
log "probing for i3 Mega and dPette (wake the dPette with its button first)"
if [ -x .venv/bin/python ]; then
    PROBE=$(.venv/bin/python tools/preflight.py --export 2>/dev/null || true)
else
    PROBE=$(uv run python tools/preflight.py --export 2>/dev/null || true)
fi
[ -n "$PROBE" ] || die "preflight found no devices. Check the powered USB hub and re-run."

resolve_by_id() {
    # /dev/ttyUSB0 → /dev/serial/by-id/usb-... (falls back to input if no match).
    local target
    target=$(readlink -f "$1")
    for s in /dev/serial/by-id/*; do
        [ -e "$s" ] || continue
        [ "$(readlink -f "$s")" = "$target" ] && { echo "$s"; return 0; }
    done
    echo "$1"
}

mkdir -p config.local
: > "$ENV_FILE"
while IFS= read -r line; do
    case "$line" in
        export\ *=*)
            var=${line#export }
            name=${var%%=*}
            value=${var#*=}
            byid=$(resolve_by_id "$value")
            echo "export ${name}=${byid}" >> "$ENV_FILE"
            log "${name} → ${byid}"
            ;;
    esac
done <<< "$PROBE"

# 8. next steps
cat <<EOF

[setup_pi] done. To run the v0 showcase against real hardware:

    cd $REPO_DIR
    source $ENV_FILE
    uv run tools/preflight.py            # sanity check on by-id paths
    uv run examples/showcase_v0_pipette_sim.py
EOF
