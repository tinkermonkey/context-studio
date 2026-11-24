#!/usr/bin/env bash
# Spike (#1671): build the bundled Python runtime and the server payload for the
# desktop app. Not the release build: it proves the layout and measures it.
#
# Usage: app/spike/build_runtime.sh <spike-dir>
#   <spike-dir>/downloads/cpython/<archive>   python-build-standalone archive (checked)
#   <spike-dir>/venv-freeze.txt               pip freeze of the dev venv (version pins)
# Produces app/spike/payload/{python,server,ui,hf} (git-ignored) for the app's Resources.
set -euo pipefail

SPIKE="$1"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DEV_SITE="${DEV_SITE:-/Users/austinsand/workspace/context-studio/local-server/.venv/lib/python3.14/site-packages}"
PAYLOAD="$REPO/app/spike/payload"
ARCHIVE="$(ls "$SPIKE"/downloads/cpython/cpython-3.14.*-aarch64-apple-darwin-install_only_stripped.tar.gz)"

rm -rf "$PAYLOAD" && mkdir -p "$PAYLOAD"

# 1. The interpreter: python-build-standalone extracts to python/.
tar -xzf "$ARCHIVE" -C "$PAYLOAD"
PY="$PAYLOAD/python/bin/python3"
"$PY" -VV

# 2. Runtime requirements: requirements.txt without dev/benchmark-only packages,
#    pinned to the dev venv's versions so the bundle runs what the tests run.
#    en_core_web_sm is copied from the dev venv instead of fetched from GitHub.
grep -vE '^(datasets|arxiv|langgraph|en_core_web_sm)' "$REPO/local-server/requirements.txt" \
  | sed 's/^sqlalchemy\[mypy\]/sqlalchemy/' > "$SPIKE/requirements-runtime.txt"
#    requirements.txt's own == pins win over the venv's versions.
PINNED="$(grep -oE '^[A-Za-z0-9_.-]+==' "$SPIKE/requirements-runtime.txt" | sed 's/==$//' | paste -sd'|' -)"
grep -viE "^(en_core_web_sm|mypy|mypy_extensions|pip|${PINNED})( |=|@)" "$SPIKE/venv-freeze.txt" > "$SPIKE/constraints.txt"

UV_CACHE_DIR="$SPIKE/downloads/uv-cache" uv pip install \
  --python "$PY" --break-system-packages \
  -r "$SPIKE/requirements-runtime.txt" -c "$SPIKE/constraints.txt"

SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
cp -R "$DEV_SITE/en_core_web_sm" "$DEV_SITE"/en_core_web_sm-*.dist-info "$SITE/"

# 3. The server: local-server's code and migrations, no tests, scripts, data or venv.
mkdir -p "$PAYLOAD/server"
rsync -a --exclude '.venv' --exclude 'tests' --exclude 'logs' --exclude '*.db*' \
  --exclude '__pycache__' --exclude 'documentation' --exclude 'config.json' --exclude '.env' \
  --exclude 'node_modules' --exclude '.pytest_cache' --exclude '.mypy_cache' \
  "$REPO/local-server/" "$PAYLOAD/server/"
cp "$REPO/app/spike/desktop_entry.py" "$PAYLOAD/server/desktop_entry.py"

# 4. Bytecode, so nothing is written into the bundle at run time.
#    unchecked-hash: the bytecode stays valid when bundling changes file times.
"$PY" -m compileall -q -j 0 --invalidation-mode unchecked-hash \
  "$PAYLOAD/python/lib" "$PAYLOAD/server" > /dev/null || true

# 5. The embedding model, as a Hugging Face cache the server reads offline: one
#    snapshot (the one refs/main names) with real files, since bundling follows links.
SRC_MODEL="$HOME/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L12-v2"
DST_MODEL="$PAYLOAD/hf/hub/models--sentence-transformers--all-MiniLM-L12-v2"
REV="$(cat "$SRC_MODEL/refs/main")"
mkdir -p "$DST_MODEL/refs" "$DST_MODEL/snapshots"
cp "$SRC_MODEL/refs/main" "$DST_MODEL/refs/main"
cp -RL "$SRC_MODEL/snapshots/$REV" "$DST_MODEL/snapshots/$REV"

# 6b. Not needed at run time: headers, tests, stubs, pip, tk/idle, links bundling would copy twice.
find "$PAYLOAD/python" -type d -name include -prune -exec rm -rf {} +
find "$PAYLOAD/python/lib/python3.14/site-packages" -type d \( -name tests -o -name test \) -prune -exec rm -rf {} +
find "$PAYLOAD/python/lib/python3.14/site-packages" -name '*.pyi' -delete
rm -rf "$PAYLOAD/python/lib/python3.14/site-packages"/pip* "$PAYLOAD/python/lib"/tcl* "$PAYLOAD/python/lib"/tk* \
  "$PAYLOAD/python/lib/python3.14"/{tkinter,idlelib,ensurepip,turtledemo} "$PAYLOAD/python/share"
find "$PAYLOAD/python/bin" -type l ! -name python3 -delete

# 6. The UI, built for the same origin as the API.
(cd "$REPO/ux" && VITE_API_BASE_URL="" npx vite build --outDir "$PAYLOAD/ui" --emptyOutDir > "$SPIKE/ui-build.log")

du -sh "$PAYLOAD"/* "$PAYLOAD"
