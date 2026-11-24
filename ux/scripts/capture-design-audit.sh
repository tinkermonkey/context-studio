#!/usr/bin/env bash
# Capture screenshot pairs for the Heimdall design audit.
#
# Saves prototype and implementation screenshots side-by-side in:
#   /screenshots/audit/YYYY-MM-DD/
#
# Usage:
#   ./scripts/capture-design-audit.sh             # capture all pages
#   ./scripts/capture-design-audit.sh dashboard   # capture one page

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DATE=$(date +%Y-%m-%d)
OUTPUT_DIR="$REPO_ROOT/screenshots/audit/$DATE"
mkdir -p "$OUTPUT_DIR"

DESIGN_PORT=3200

# In a git worktree the app under test is the QA instance from `./dev.sh --worktree`
# (ports in .qa-instance/state); never start servers on the default ports there.
# In the main checkout the defaults apply and missing servers are started.
if [[ "$(git -C "$REPO_ROOT" rev-parse --git-dir)" != "$(git -C "$REPO_ROOT" rev-parse --git-common-dir)" ]]; then
  QA_STATE="$REPO_ROOT/.qa-instance/state"
  if [[ ! -f "$QA_STATE" ]]; then
    echo "No QA instance in this worktree. Start one with: ./dev.sh --worktree --from-workspace" >&2
    exit 1
  fi
  APP_PORT="$(sed -n 's/^FRONTEND_PORT=//p' "$QA_STATE" | tail -1)"
  BACKEND_PORT="$(sed -n 's/^BACKEND_PORT=//p' "$QA_STATE" | tail -1)"
  IN_WORKTREE=1
else
  APP_PORT=3100
  BACKEND_PORT=8000
  IN_WORKTREE=0
fi

# ── Ensure servers are running ─────────────────────────────────────────────────

if [[ "$IN_WORKTREE" == 0 ]] && ! lsof -ti ":$BACKEND_PORT" > /dev/null 2>&1; then
  echo "Starting backend on :$BACKEND_PORT..."
  cd "$REPO_ROOT/local-server"
  source .venv/bin/activate
  python app.py > /tmp/backend.log 2>&1 &
  sleep 5
  cd "$REPO_ROOT/ux"
fi

if [[ "$IN_WORKTREE" == 0 ]] && ! lsof -ti ":$APP_PORT" > /dev/null 2>&1; then
  echo "Starting Vite dev server on :$APP_PORT..."
  cd "$REPO_ROOT/ux"
  npm run dev > /tmp/vite-dev.log 2>&1 &
  sleep 6
fi

if ! lsof -ti ":$DESIGN_PORT" > /dev/null 2>&1; then
  echo "Serving design prototype on :$DESIGN_PORT..."
  cd "$REPO_ROOT/ux/design"
  python3 -m http.server $DESIGN_PORT > /tmp/design-server.log 2>&1 &
  sleep 2
fi

cd "$REPO_ROOT/ux"

# ── Page definitions: "name|impl_route|proto_hash" ───────────────────────────

PAGES=(
  "dashboard|/app|dashboard"
  "schema-classes|/app/schema/classes|schema-classes"
  "schema-taxonomies|/app/schema/taxonomies|schema-classes"
  "pipelines|/app/pipelines|pipelines"
  "settings|/app/settings|settings"
  "graph|/app/graph|graph"
)

# ── Capture via Node/Playwright ───────────────────────────────────────────────

PAGE_FILTER="${1:-}"

capture_page() {
  local name="$1"
  local impl_route="$2"
  local proto_hash="$3"

  echo "  → $name"

  node - <<NODEEOF
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  // 2400px height so shell canvas scroll container is fully visible
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 2400 } });

  // Prototype
  const proto = await ctx.newPage();
  await proto.goto('http://localhost:${DESIGN_PORT}/Context%20Studio.html#r=${proto_hash}');
  await proto.waitForTimeout(1500);
  await proto.screenshot({ path: '${OUTPUT_DIR}/${name}-prototype.png', fullPage: true });

  // Implementation — set workspace in localStorage before scripts run
  const impl = await ctx.newPage();
  await impl.addInitScript(() => {
    localStorage.setItem('context-studio:workspace-path', './local.db');
  });
  await impl.goto('http://localhost:${APP_PORT}${impl_route}');
  await impl.waitForLoadState('networkidle');
  await impl.waitForTimeout(800);

  // Handle workspace picker if it still appears
  try {
    const picker = impl.locator('button:has-text("local.db")');
    if (await picker.isVisible({ timeout: 2000 })) {
      await picker.click();
      await impl.waitForLoadState('networkidle');
      await impl.waitForTimeout(500);
    }
  } catch (_) {}

  await impl.screenshot({ path: '${OUTPUT_DIR}/${name}-impl.png', fullPage: true });
  await browser.close();
})().catch(e => { console.error('${name}:', e.message); process.exit(1); });
NODEEOF
}

# ── Run captures ──────────────────────────────────────────────────────────────

echo ""
echo "Capturing design audit screenshots → $OUTPUT_DIR"
echo ""

for entry in "${PAGES[@]}"; do
  name="${entry%%|*}"
  rest="${entry#*|}"
  impl_route="${rest%%|*}"
  proto_hash="${rest##*|}"

  if [[ -z "$PAGE_FILTER" || "$PAGE_FILTER" == "$name" ]]; then
    capture_page "$name" "$impl_route" "$proto_hash"
  fi
done

echo ""
echo "Done. Pairs saved to $OUTPUT_DIR:"
for f in "$OUTPUT_DIR"/*-prototype.png; do
  [[ -f "$f" ]] || continue
  name="$(basename "${f%-prototype.png}")"
  echo "  $name: ${name}-prototype.png  ↔  ${name}-impl.png"
done
echo ""
echo "Run conformance tests: cd ux && npm run design-audit"
