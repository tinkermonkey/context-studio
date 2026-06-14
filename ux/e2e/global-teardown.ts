import { execSync } from "node:child_process";

/**
 * E2E harness teardown — stops the isolated test stack started by
 * global-setup (backend :8888, frontend :3888) by port. The dev servers on
 * :8000/:3100 are never targeted. The test DBs under datafiles/e2e-test are
 * left in place (disposable; recreated/migrated on the next run).
 */
function killPort(port: number): void {
  try {
    const pids = execSync(`lsof -ti tcp:${port} || true`, { encoding: "utf8" }).trim();
    if (pids) {
      execSync(`kill -9 ${pids.split("\n").join(" ")}`);
      console.log(`[e2e] stopped process(es) on :${port}`);
    }
  } catch {
    // Best-effort — nothing listening, or already gone.
  }
}

export default function globalTeardown() {
  killPort(8888);
  killPort(3888);
  console.log("[e2e] isolated stack stopped");
}
