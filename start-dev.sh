#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/linux-gateway/.venv"
CHANNEL="vcan0"
HOST="127.0.0.1"
PORT="8000"
CELLS="48"
START_SIM="1"
PORT_SET="0"

usage() {
  cat <<EOF
Usage: ./start-dev.sh [options]

Options:
  --host HOST       Uvicorn host. Default: 127.0.0.1
  --port PORT       Uvicorn port. Default: 8000
  --channel NAME    SocketCAN channel. Default: vcan0
  --cells COUNT     Simulated cell count. Default: 48
  --no-sim          Start only the web gateway, without CAN simulator
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"
      shift 2
      ;;
    --port)
      PORT="$2"
      PORT_SET="1"
      shift 2
      ;;
    --channel)
      CHANNEL="$2"
      shift 2
      ;;
    --cells)
      CELLS="$2"
      shift 2
      ;;
    --no-sim)
      START_SIM="0"
      shift
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

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing command: $1" >&2
    exit 1
  fi
}

ensure_venv() {
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Creating Python virtualenv..."
    python3 -m venv "$VENV_DIR"
  fi

  if [[ ! -x "$VENV_DIR/bin/uvicorn" ]]; then
    echo "Installing Python dependencies..."
    "$VENV_DIR/bin/pip" install -r "$ROOT_DIR/linux-gateway/requirements.txt"
  fi
}

ensure_vcan() {
  if ip link show "$CHANNEL" >/dev/null 2>&1; then
    echo "$CHANNEL is already available."
    return
  fi

  echo "Creating $CHANNEL. Sudo password may be requested."
  sudo modprobe vcan
  sudo ip link add dev "$CHANNEL" type vcan
  sudo ip link set up "$CHANNEL"
}

port_in_use() {
  if ss -ltn "( sport = :$PORT )" | grep -q ":$PORT"; then
    return 0
  fi
  return 1
}

choose_port() {
  if ! port_in_use; then
    return
  fi

  if [[ "$PORT_SET" == "1" ]]; then
    echo "Port $PORT is already in use. Use another --port value or stop the running service." >&2
    exit 1
  fi

  local candidate
  for candidate in $(seq 8001 8020); do
    PORT="$candidate"
    if ! port_in_use; then
      echo "Port 8000 is busy, using $PORT instead."
      return
    fi
  done

  echo "No free port found in range 8000-8020." >&2
  exit 1
}

cleanup() {
  if [[ -n "${SIM_PID:-}" ]]; then
    kill "$SIM_PID" >/dev/null 2>&1 || true
    wait "$SIM_PID" >/dev/null 2>&1 || true
  fi
}

need_command python3
need_command ip
need_command ss
ensure_venv
ensure_vcan
choose_port

trap cleanup EXIT INT TERM

if [[ "$START_SIM" == "1" ]]; then
  echo "Starting CAN simulator on $CHANNEL with $CELLS cells..."
  "$VENV_DIR/bin/python" "$ROOT_DIR/tools/can-simulator/send_status.py" \
    --channel "$CHANNEL" \
    --cells "$CELLS" &
  SIM_PID="$!"
fi

echo "Starting EV Battery Service Gateway..."
echo "Open: http://$HOST:$PORT"
cd "$ROOT_DIR/linux-gateway"
exec "$VENV_DIR/bin/uvicorn" app.main:app --host "$HOST" --port "$PORT"
