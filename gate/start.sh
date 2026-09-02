#!/usr/bin/env bash
# Start the fullscreen gate scanner.
# Designed for Raspberry Pi desktop autostart / SSH-managed kiosks.

set -u

GATE_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/chudartz-gate"
LOG_FILE="$LOG_DIR/startup.log"
mkdir -p "$LOG_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$GATE_DIR" || exit 1

log "Starting Chudartz gate from $GATE_DIR"

export DISPLAY="${DISPLAY:-:0}"
# -u keeps output unbuffered so heartbeat lines reach the log as they happen.
exec /usr/bin/python3 -u "$GATE_DIR/main.py" 2>&1 | tee -a "$LOG_FILE"
