import { spawn, execSync } from "node:child_process";
import { openSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

/**
 * E2E harness — boots an ISOLATED test stack so specs never touch the dev
 * servers or a developer's data:
 *
 *   - backend on :8888 using config.e2e.json (its own datafiles/e2e-test DBs)
 *   - frontend on :3888 pointed at :8888 (Vite `e2e` mode → .env.e2e)
 *
 * The fixtures (e2e/fixtures/api-client.ts) and the UI both talk to :8888.
 * global-teardown stops both servers by port. Dev servers on :8000/:3100 are
 * left untouched.
 */
const UX_DIR = process.cwd();
const BACKEND_DIR = resolve(UX_DIR, "../local-server");
const VENV_PYTHON = resolve(BACKEND_DIR, ".venv/bin/python");
const LOG_DIR = resolve(UX_DIR, "e2e/.logs");

const BACKEND_HEALTH = "http://localhost:8888/api/v1/admin/health";
const FRONTEND_URL = "http://localhost:3888";

async function waitForUrl(url: string, timeoutMs: number, label: string): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastErr = "";
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
      lastErr = `HTTP ${res.status}`;
    } catch (err) {
      lastErr = err instanceof Error ? err.message : String(err);
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`Timed out waiting for ${label} at ${url} (last: ${lastErr})`);
}

export default async function globalSetup() {
  mkdirSync(LOG_DIR, { recursive: true });

  // 0. Reset the isolated test DBs so each run starts from a clean, current
  // schema (avoids drift from a previously-stamped revision).
  const TEST_DB_DIR = resolve(BACKEND_DIR, "datafiles/e2e-test");
  mkdirSync(TEST_DB_DIR, { recursive: true });
  for (const db of ["local.db", "operations.db"]) {
    for (const ext of ["", "-wal", "-shm"]) {
      rmSync(resolve(TEST_DB_DIR, db + ext), { force: true });
    }
  }

  // 1. Bring the isolated test DBs up to the current schema (base → head).
  console.log("[e2e] migrating test databases…");
  for (const [target, url] of [
    ["local", "sqlite:///./datafiles/e2e-test/local.db"],
    ["operations", "sqlite:///./datafiles/e2e-test/operations.db"],
  ] as const) {
    const flag = target === "local" ? "--local-db-url" : "--operations-db-url";
    execSync(`${VENV_PYTHON} scripts/run_migrations.py ${target} upgrade head ${flag} ${url}`, {
      cwd: BACKEND_DIR,
      stdio: "inherit",
      env: { ...process.env, PYTHONPATH: BACKEND_DIR },
    });
  }

  // 2. Start the test backend on :8888.
  console.log("[e2e] starting backend on :8888 (config.e2e.json)…");
  const backendLog = openSync(resolve(LOG_DIR, "backend.log"), "w");
  const backend = spawn(VENV_PYTHON, ["app.py"], {
    cwd: BACKEND_DIR,
    env: { ...process.env, CONFIG_PATH: "./config.e2e.json", PYTHONUNBUFFERED: "1" },
    detached: true,
    stdio: ["ignore", backendLog, backendLog],
  });
  backend.unref();
  await waitForUrl(BACKEND_HEALTH, 90000, "test backend");
  console.log("[e2e] backend ready");

  // 3. Start the test frontend on :3888 pointed at :8888.
  console.log("[e2e] starting frontend on :3888 (mode=e2e → :8888)…");
  const frontendLog = openSync(resolve(LOG_DIR, "frontend.log"), "w");
  const frontend = spawn(
    "npm",
    ["run", "dev", "--", "--port", "3888", "--mode", "e2e", "--strictPort"],
    {
      cwd: UX_DIR,
      env: { ...process.env, VITE_API_BASE_URL: "http://localhost:8888" },
      detached: true,
      stdio: ["ignore", frontendLog, frontendLog],
    },
  );
  frontend.unref();
  await waitForUrl(FRONTEND_URL, 60000, "test frontend");
  console.log("[e2e] frontend ready — isolated stack up (:8888 / :3888)");
}
