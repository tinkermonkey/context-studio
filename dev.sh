#!/usr/bin/env bash
# Start the Context Studio back end (port 8000) and front end (port 3100).
#
# Usage: ./dev.sh [--migrate]
#   --migrate   upgrade local.db and operations.db to head before starting
#
# The back end runs from local-server/ so it reads local-server/config.json
# and local-server/.env. Ctrl-C stops both servers.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$ROOT/local-server"
UX_DIR="$ROOT/ux"
BACKEND_PORT=8000
FRONTEND_PORT=3100
HEALTH_URL="http://127.0.0.1:$BACKEND_PORT/api/v1/admin/health"

migrate=false
for arg in "$@"; do
  case "$arg" in
    --migrate) migrate=true ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

fail() { echo "error: $*" >&2; exit 1; }

[[ -x "$SERVER_DIR/.venv/bin/python" ]] || fail "missing local-server/.venv — run: cd local-server && python -m venv .venv && .venv/bin/pip install -r requirements.txt"
[[ -f "$SERVER_DIR/config.json" ]] || fail "missing local-server/config.json"
[[ -x "$UX_DIR/node_modules/.bin/vite" ]] || fail "missing ux/node_modules — run: cd ux && npm install"

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    fail "port $port is already in use (lsof -nP -iTCP:$port -sTCP:LISTEN)"
  fi
done

if $migrate; then
  echo "==> Running migrations"
  (cd "$SERVER_DIR" && .venv/bin/python scripts/run_migrations.py all upgrade head)
fi

pids=()
cleanup() {
  trap - INT TERM EXIT
  echo
  echo "==> Stopping servers"
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> Starting back end on :$BACKEND_PORT (logs also in local-server/logs/context_studio.log)"
(cd "$SERVER_DIR" && exec .venv/bin/python app.py) &
pids+=($!)

echo "==> Starting front end on :$FRONTEND_PORT"
(cd "$UX_DIR" && exec ./node_modules/.bin/vite --port="$FRONTEND_PORT") &
pids+=($!)

# Report when the back end is ready; startup loads models and can take a while.
for _ in $(seq 1 180); do
  if curl -fs "$HEALTH_URL" >/dev/null 2>&1; then
    echo "==> Ready: http://localhost:$FRONTEND_PORT (API http://localhost:$BACKEND_PORT)"
    break
  fi
  kill -0 "${pids[0]}" 2>/dev/null || fail "back end exited during startup"
  sleep 1
done

# Exit (and stop the other server) as soon as either one stops.
while kill -0 "${pids[0]}" 2>/dev/null && kill -0 "${pids[1]}" 2>/dev/null; do
  sleep 1
done
echo "==> A server stopped; shutting down the other"
