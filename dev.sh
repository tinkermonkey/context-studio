#!/usr/bin/env bash
# Start the Context Studio back end (port 8000) and front end (port 3100).
#
# Usage: ./dev.sh [--migrate]
#   --migrate   upgrade local.db and operations.db to head before starting
#
# The back end runs from local-server/ so it reads local-server/config.json
# and local-server/.env. Ctrl-C stops both servers.
#
# QA instance from a git worktree, beside the main checkout's servers:
#   ./dev.sh --worktree [--from-workspace] [--port-offset N]
#       Link the venv, local-server/.env and node_modules from the main
#       checkout, create migrated databases in .qa-instance/ (with
#       --from-workspace: snapshots of the main checkout's workspace), write
#       .qa-instance/config.json, start both servers in the background on
#       8000+N and 3100+N (default N: the first free of 10, 20, ...) and print
#       the URLs. The main checkout's databases are only ever read.
#   ./dev.sh --worktree --setup             only link the venv, .env and node_modules
#                                           (enough for tests and the E2E harness)
#   ./dev.sh --worktree --restart-backend   re-migrate the copies, restart the back end
#   ./dev.sh --worktree --stop              stop both servers, remove .qa-instance/
#                                           and the links the command created

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SERVER_DIR="$ROOT/local-server"
UX_DIR="$ROOT/ux"
BACKEND_PORT=8000
FRONTEND_PORT=3100
HEALTH_URL="http://127.0.0.1:$BACKEND_PORT/api/v1/admin/health"

fail() { echo "error: $*" >&2; exit 1; }
usage() { awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; }

migrate=false
worktree=false
from_workspace=false
port_offset=""
action=start
while [[ $# -gt 0 ]]; do
  case "$1" in
    --migrate) migrate=true ;;
    --worktree) worktree=true ;;
    --from-workspace) from_workspace=true ;;
    --port-offset) [[ $# -ge 2 ]] || fail "--port-offset needs a number"; port_offset="$2"; shift ;;
    --port-offset=*) port_offset="${1#*=}" ;;
    --setup) action=setup; worktree=true ;;
    --restart-backend) action=restart-backend; worktree=true ;;
    --stop) action=stop; worktree=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

if ! $worktree && { $from_workspace || [[ -n "$port_offset" ]]; }; then
  fail "--from-workspace and --port-offset need --worktree"
fi

# ---------------------------------------------------------------------------
# QA instance from a git worktree
# ---------------------------------------------------------------------------

STATE_DIR="$ROOT/.qa-instance"
STATE_FILE="$STATE_DIR/state"
LINKS_FILE="$STATE_DIR/links"

# Set MAIN to the main checkout, refusing to run in the main checkout itself.
require_worktree() {
  local git_dir common_dir
  git_dir="$(git -C "$ROOT" rev-parse --path-format=absolute --git-dir 2>/dev/null)" \
    || fail "$ROOT is not a git checkout"
  common_dir="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir)"
  MAIN="$(cd "$common_dir/.." && pwd -P)"
  if [[ "$git_dir" == "$common_dir" || "$ROOT" == "$MAIN" ]]; then
    fail "this is the main checkout. --worktree runs only from a git worktree, so it can never touch the workspace databases or servers here."
  fi
  [[ -d "$MAIN/local-server" ]] || fail "main checkout not found at $MAIN"
}

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

state_get() { [[ -f "$STATE_FILE" ]] || return 0; sed -n "s/^$1=//p" "$STATE_FILE" | tail -1; }
state_set() {
  touch "$STATE_FILE"
  grep -v "^$1=" "$STATE_FILE" >"$STATE_FILE.tmp" || true
  echo "$1=$2" >>"$STATE_FILE.tmp"
  mv "$STATE_FILE.tmp" "$STATE_FILE"
}

# True when the pid is alive and is the server we started (guards against pid reuse).
is_our_server() {
  local pid="$1" pattern="$2"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && ps -o command= -p "$pid" | grep -q -- "$pattern"
}

record_link() { mkdir -p "$STATE_DIR"; echo "$1" >>"$LINKS_FILE"; }
is_recorded() { [[ -f "$LINKS_FILE" ]] && grep -qx -- "$1" "$LINKS_FILE"; }

# Link one path (relative to the repo root) to the main checkout's copy.
link_from_main() {
  local rel="$1" dst="$ROOT/$1" src="$MAIN/$1"
  if [[ -e "$dst" || -L "$dst" ]]; then
    echo "    $rel: already present, kept$(is_recorded "$rel" && echo " (linked by an earlier run)")"
  elif [[ -e "$src" ]]; then
    ln -s "$src" "$dst"
    record_link "$rel"
    echo "    $rel -> main checkout"
  else
    return 1
  fi
}

setup_links() {
  echo "==> Linking dependencies from the main checkout ($MAIN)"
  mkdir -p "$STATE_DIR"

  if ! link_from_main local-server/.venv; then
    echo "    local-server/.venv: none in the main checkout, creating one"
    python3 -m venv "$SERVER_DIR/.venv"
    record_link local-server/.venv
    "$SERVER_DIR/.venv/bin/pip" install -q -r "$SERVER_DIR/requirements.txt"
  fi
  if [[ -L "$SERVER_DIR/.venv" ]] && ! cmp -s "$SERVER_DIR/requirements.txt" "$MAIN/local-server/requirements.txt"; then
    echo "    warning: requirements.txt differs from the main checkout; the linked venv may lack new packages"
  fi

  link_from_main local-server/.env || echo "    local-server/.env: none in the main checkout, skipped"

  # node_modules: a real folder of per-package links, so Vite's cache
  # (node_modules/.vite) is written in this worktree, not the main checkout.
  local nm="$UX_DIR/node_modules" main_nm="$MAIN/ux/node_modules" entry
  if [[ -e "$nm" || -L "$nm" ]]; then
    echo "    ux/node_modules: already present, kept$(is_recorded ux/node_modules && echo " (linked by an earlier run)")"
  elif [[ -d "$main_nm" ]] && cmp -s "$UX_DIR/package-lock.json" "$MAIN/ux/package-lock.json"; then
    mkdir "$nm"
    record_link ux/node_modules
    for entry in "$main_nm"/* "$main_nm/.bin"; do
      if [[ -e "$entry" ]]; then ln -s "$entry" "$nm/$(basename "$entry")"; fi
    done
    echo "    ux/node_modules -> main checkout (per package)"
  else
    echo "    ux/node_modules: package-lock.json differs from the main checkout (or it has none), running npm ci"
    record_link ux/node_modules
    (cd "$UX_DIR" && npm ci --no-audit --no-fund --loglevel=error)
  fi
}

remove_links() {
  [[ -f "$LINKS_FILE" ]] || return 0
  local rel dst
  while IFS= read -r rel; do
    [[ -n "$rel" ]] || continue
    dst="$ROOT/$rel"
    case "$rel" in
      local-server/.venv|local-server/.env|ux/node_modules) ;;
      *) echo "    skipped unexpected entry: $rel"; continue ;;
    esac
    if [[ -L "$dst" ]]; then
      rm "$dst"
    elif [[ -d "$dst" ]]; then
      rm -rf "$dst"  # our per-package link folder, a created venv or an npm ci install
    fi
    echo "    removed $rel"
  done <"$LINKS_FILE"
}

# Read the main checkout's database paths (config.json, else the defaults),
# resolved against its local-server/. Prints "local_db<TAB>operations_db".
main_db_paths() {
  "$SERVER_DIR/.venv/bin/python" - "$MAIN/local-server" <<'PY'
import json, os, sys
server_dir = sys.argv[1]
db = {}
path = os.path.join(server_dir, "config.json")
if os.path.exists(path) and os.path.getsize(path) > 0:
    with open(path) as f:
        db = json.load(f).get("database") or {}
def resolve(value, default):
    return os.path.realpath(os.path.join(server_dir, os.path.expanduser(value or default)))
print(resolve(db.get("local_db_path"), "./local.db") + "\t" + resolve(db.get("operations_db_path"), "./operations.db"))
PY
}

snapshot_workspace() {
  local paths src_local src_ops
  paths="$(main_db_paths)"
  src_local="${paths%%$'\t'*}"
  src_ops="${paths#*$'\t'}"
  [[ -f "$src_local" ]] || fail "the main checkout's local.db was not found"
  echo "==> Snapshotting the workspace databases into .qa-instance/ (read only)"
  sqlite3 -readonly "$src_local" ".backup '$STATE_DIR/local.db'"
  if [[ -f "$src_ops" ]]; then
    sqlite3 -readonly "$src_ops" ".backup '$STATE_DIR/operations.db'"
  fi
  # Saved source originals live beside local.db.
  if [[ -d "$(dirname "$src_local")/sources" ]]; then
    cp -R "$(dirname "$src_local")/sources" "$STATE_DIR/sources"
  fi
}

# Upgrade the copies to head. The URLs are explicit: run_migrations.py would
# otherwise default to ./local.db. Refuses any path outside .qa-instance/.
migrate_copies() {
  local db
  for db in "$STATE_DIR/local.db" "$STATE_DIR/operations.db"; do
    [[ "$(cd "$(dirname "$db")" && pwd -P)" == "$STATE_DIR" && "$STATE_DIR" == "$ROOT/.qa-instance" ]] \
      || fail "refusing to migrate $db: not in this worktree's .qa-instance/"
  done
  echo "==> Migrating the copies to head"
  (cd "$SERVER_DIR" && .venv/bin/python scripts/run_migrations.py all upgrade head \
    --local-db-url "sqlite:///$STATE_DIR/local.db" \
    --operations-db-url "sqlite:///$STATE_DIR/operations.db") >"$STATE_DIR/migrate.log" 2>&1 \
    || { tail -20 "$STATE_DIR/migrate.log" >&2; fail "migration failed (log: .qa-instance/migrate.log)"; }
}

# Write .qa-instance/config.json from this worktree's config.json, else the
# main checkout's, else config.example.json, pointing everything the instance
# writes into .qa-instance/.
write_config() {
  local base
  for base in "$SERVER_DIR/config.json" "$MAIN/local-server/config.json" "$SERVER_DIR/config.example.json"; do
    [[ -s "$base" ]] && break
  done
  echo "==> Writing .qa-instance/config.json (from ${base#"$MAIN"/})"
  "$SERVER_DIR/.venv/bin/python" - "$base" "$STATE_DIR" "$1" "$2" <<'PY'
import json, os, sys
base, state_dir, backend_port, frontend_port = sys.argv[1:]
with open(base) as f:
    config = json.load(f)
server = config.setdefault("server", {})
server["port"] = int(backend_port)
server["ui_base_url"] = f"http://localhost:{frontend_port}"
server.pop("cors_origins", None)  # follow ui_base_url only
database = config.setdefault("database", {})
database["local_db_path"] = os.path.join(state_dir, "local.db")
database["operations_db_path"] = os.path.join(state_dir, "operations.db")
reference = config.setdefault("reference", {})
reference["reference_db_path"] = os.path.join(state_dir, "reference.db")
reference.setdefault("proxy", {})["cache_db_path"] = os.path.join(state_dir, "reference_api_cache.db")
config.pop("sync", None)  # never sync a QA copy to the workspace's remote
path = os.path.join(state_dir, "config.json")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    json.dump(config, f, indent=2)
PY
}

# Wait for a URL to answer 200 while the process stays up.
wait_healthy() {
  local url="$1" pid="$2" timeout="$3" i
  for ((i = 0; i < timeout; i++)); do
    if curl -fs --max-time 2 "$url" >/dev/null 2>&1; then
      return 0
    fi
    kill -0 "$pid" 2>/dev/null || return 1
    sleep 1
  done
  return 1
}

start_backend() {
  local port pid
  port="$(state_get BACKEND_PORT)"
  (cd "$SERVER_DIR" && CONFIG_PATH="$STATE_DIR/config.json" PYTHONUNBUFFERED=1 \
    exec nohup .venv/bin/python app.py >>"$STATE_DIR/backend.log" 2>&1 </dev/null) &
  pid=$!
  state_set BACKEND_PID "$pid"
  echo "==> Starting back end on :$port (log: .qa-instance/backend.log)"
  if ! wait_healthy "http://127.0.0.1:$port/api/v1/admin/health" "$pid" 180; then
    tail -20 "$STATE_DIR/backend.log" >&2
    stop_server BACKEND_PID app.py
    fail "back end did not become healthy. Files are kept; run ./dev.sh --worktree --stop to clean up."
  fi
}

start_frontend() {
  local port backend_port pid
  port="$(state_get FRONTEND_PORT)"
  backend_port="$(state_get BACKEND_PORT)"
  # VITE_API_BASE_URL sets both the API client's base URL and the /api proxy target.
  (cd "$UX_DIR" && VITE_API_BASE_URL="http://localhost:$backend_port" \
    exec nohup ./node_modules/.bin/vite --port="$port" --strictPort >"$STATE_DIR/frontend.log" 2>&1 </dev/null) &
  pid=$!
  state_set FRONTEND_PID "$pid"
  echo "==> Starting front end on :$port (log: .qa-instance/frontend.log)"
  if ! wait_healthy "http://localhost:$port/" "$pid" 60; then
    tail -20 "$STATE_DIR/frontend.log" >&2
    stop_server FRONTEND_PID vite
    stop_server BACKEND_PID app.py
    fail "front end did not start. Files are kept; run ./dev.sh --worktree --stop to clean up."
  fi
}

stop_server() {
  local key="$1" pattern="$2" pid i
  pid="$(state_get "$key")"
  if is_our_server "$pid" "$pattern"; then
    kill "$pid" 2>/dev/null || true
    for ((i = 0; i < 20; i++)); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    kill -9 "$pid" 2>/dev/null || true
    echo "    stopped $pattern (pid $pid)"
  fi
  [[ -f "$STATE_FILE" ]] && state_set "$key" ""
}

choose_ports() {
  local offset
  if [[ -n "$port_offset" ]]; then
    [[ "$port_offset" =~ ^[0-9]+$ ]] && ((port_offset >= 1 && port_offset <= 999)) \
      || fail "--port-offset must be a number from 1 to 999"
    offset="$port_offset"
  else
    for offset in $(seq 10 10 190) ""; do
      [[ -n "$offset" ]] || fail "no free port pair found for offsets 10..190; pass --port-offset"
      port_in_use $((BACKEND_PORT + offset)) || port_in_use $((FRONTEND_PORT + offset)) || break
    done
  fi
  QA_BACKEND_PORT=$((BACKEND_PORT + offset))
  QA_FRONTEND_PORT=$((FRONTEND_PORT + offset))
  local port
  for port in "$QA_BACKEND_PORT" "$QA_FRONTEND_PORT"; do
    port_in_use "$port" && fail "port $port is already in use (lsof -nP -iTCP:$port -sTCP:LISTEN)"
  done
  return 0
}

print_urls() {
  echo "==> QA instance ready"
  echo "    UI   http://localhost:$(state_get FRONTEND_PORT)"
  echo "    API  http://localhost:$(state_get BACKEND_PORT)"
  echo "    Data .qa-instance/ ($(state_get SOURCE))"
  echo "    Restart the back end: ./dev.sh --worktree --restart-backend"
  echo "    Stop and clean up:    ./dev.sh --worktree --stop"
}

worktree_start() {
  if [[ -f "$STATE_FILE" ]]; then
    if is_our_server "$(state_get BACKEND_PID)" app.py || is_our_server "$(state_get FRONTEND_PID)" vite; then
      fail "a QA instance is already running here (UI :$(state_get FRONTEND_PORT)). Use --restart-backend or --stop."
    fi
    fail ".qa-instance/ is left from an earlier instance. Run ./dev.sh --worktree --stop first."
  fi
  choose_ports
  [[ "$QA_BACKEND_PORT" != 8000 && "$QA_FRONTEND_PORT" != 3100 ]] || fail "refusing the main ports 8000/3100"
  command -v sqlite3 >/dev/null || fail "sqlite3 is not installed"

  setup_links
  [[ -x "$UX_DIR/node_modules/.bin/vite" ]] || fail "ux/node_modules has no vite"

  state_set BACKEND_PORT "$QA_BACKEND_PORT"
  state_set FRONTEND_PORT "$QA_FRONTEND_PORT"
  if $from_workspace; then
    snapshot_workspace
    state_set SOURCE "snapshot of the workspace"
  else
    state_set SOURCE "fresh databases"
  fi
  migrate_copies
  write_config "$QA_BACKEND_PORT" "$QA_FRONTEND_PORT"
  start_backend
  start_frontend
  print_urls
}

worktree_restart_backend() {
  [[ -f "$STATE_FILE" ]] || fail "no QA instance in this worktree; start one with ./dev.sh --worktree"
  local port
  port="$(state_get BACKEND_PORT)"
  echo "==> Restarting the back end on :$port"
  stop_server BACKEND_PID app.py
  port_in_use "$port" && fail "port $port is still in use by another process"
  migrate_copies
  start_backend
  print_urls
}

worktree_stop() {
  if [[ ! -d "$STATE_DIR" ]]; then
    echo "No QA instance or links in this worktree."
    return 0
  fi
  echo "==> Stopping the QA instance"
  stop_server FRONTEND_PID vite
  stop_server BACKEND_PID app.py
  remove_links
  rm -rf "$STATE_DIR"
  echo "    removed .qa-instance/ (database copies, config, logs)"
}

if $worktree; then
  $migrate && fail "--migrate is for the main servers; --worktree always migrates its copies"
  if [[ "$action" != start ]] && { $from_workspace || [[ -n "$port_offset" ]]; }; then
    fail "--from-workspace and --port-offset apply only when starting an instance"
  fi
  require_worktree
  case "$action" in
    start) worktree_start ;;
    setup) setup_links; echo "==> Linked. Run ./dev.sh --worktree --stop to remove the links." ;;
    restart-backend) worktree_restart_backend ;;
    stop) worktree_stop ;;
  esac
  exit 0
fi

# ---------------------------------------------------------------------------
# Main servers (8000/3100)
# ---------------------------------------------------------------------------

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
