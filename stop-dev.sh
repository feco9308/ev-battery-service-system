#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANNEL="vcan0"
REMOVE_VCAN="0"

usage() {
  cat <<EOF
Usage: ./stop-dev.sh [options]

Options:
  --remove-vcan     Also remove the vcan0 interface
  --channel NAME    SocketCAN channel to remove with --remove-vcan. Default: vcan0
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove-vcan)
      REMOVE_VCAN="1"
      shift
      ;;
    --channel)
      CHANNEL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

find_pids() {
  pgrep -f "$1" || true
}

stop_pids() {
  local label="$1"
  shift
  local pids=("$@")

  if [[ "${#pids[@]}" -eq 0 ]]; then
    echo "No $label process found."
    return
  fi

  echo "Stopping $label: ${pids[*]}"
  kill "${pids[@]}" >/dev/null 2>&1 || true
  sleep 0.5

  local still_running=()
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      still_running+=("$pid")
    fi
  done

  if [[ "${#still_running[@]}" -gt 0 ]]; then
    echo "Force stopping $label: ${still_running[*]}"
    kill -9 "${still_running[@]}" >/dev/null 2>&1 || true
  fi
}

mapfile -t gateway_pids < <(find_pids "$ROOT_DIR/linux-gateway/.venv/bin/uvicorn app.main:app")
mapfile -t simulator_pids < <(find_pids "$ROOT_DIR/tools/can-simulator/send_status.py")

stop_pids "gateway" "${gateway_pids[@]}"
stop_pids "CAN simulator" "${simulator_pids[@]}"

if [[ "$REMOVE_VCAN" == "1" ]]; then
  if ip link show "$CHANNEL" >/dev/null 2>&1; then
    echo "Removing $CHANNEL. Sudo password may be requested."
    sudo ip link delete "$CHANNEL"
  else
    echo "$CHANNEL does not exist."
  fi
fi

echo "Development services stopped."
