#!/usr/bin/env bash
# Pull latest gate code, then start the fullscreen scanner.
# Designed for Raspberry Pi desktop autostart / SSH-managed kiosks.

set -u

GATE_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$GATE_DIR/.." && pwd)"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/chudartz-gate"
LOG_FILE="$LOG_DIR/startup.log"
mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$GATE_DIR" || exit 1

log "Starting Chudartz gate from $GATE_DIR"

# Wait briefly for network (Wi-Fi can lag after boot)
if [[ "${CHUDARTZ_GATE_SKIP_PULL:-}" != "1" ]]; then
  for i in 1 2 3 4 5 6; do
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 \
      || ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
      break
    fi
    log "Waiting for network… ($i)"
    sleep 2
  done

  if git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    log "git pull in $REPO_DIR"
    # Prefer fast-forward only so local edits never get clobbered unexpectedly
    if git -C "$REPO_DIR" pull --ff-only >>"$LOG_FILE" 2>&1; then
      log "git pull OK ($(git -C "$REPO_DIR" rev-parse --short HEAD))"
    else
      log "git pull failed — starting with existing code"
    fi
  else
    log "Not a git repo at $REPO_DIR — skipping pull"
  fi
else
  log "CHUDARTZ_GATE_SKIP_PULL=1 — skipping git pull"
fi

export DISPLAY="${DISPLAY:-:0}"
exec /usr/bin/python3 "$GATE_DIR/main.py"
