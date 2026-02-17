#!/usr/bin/env bash
# SSH-based read-only collector for Cisco IOS/IOS-XE.
# Usage: ./cli_collect.sh devices.csv show_cmds.txt [outdir]
set -euo pipefail
CSV="${1:-devices.csv}"
CMDS="${2:-show_cmds.txt}"
OUTDIR="${3:-cli_out}"
mkdir -p "$OUTDIR"

# iterate CSV, skip header
 tail -n +2 "$CSV" | while IFS=',' read -r NAME IP USER PORT; do
  DEV_DIR="${OUTDIR}/${NAME}_${IP}"
  mkdir -p "$DEV_DIR"
  # Send a here-doc so all commands run in a single session on the switch
  ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -p "$PORT" "${USER}@${IP}"   > "${DEV_DIR}/session.txt" <<EOS
$(cat "$CMDS")
EOS
  # split into per-command files for easier parsing
  awk '/^show /{gsub(/[^A-Za-z0-9_. -]/,"_",$0); f=$0".txt"; print > f; next} {print >> f}'       "${DEV_DIR}/session.txt"
 done