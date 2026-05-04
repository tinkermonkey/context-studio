import { spawn, ChildProcess, execSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let backendProcess: ChildProcess | null = null;
let frontendProcess: ChildProcess | null = null;

/**
 * Wait for a URL to respond with a successful status code.
 */
async function waitForUrl(url: string, timeout: number = 30000): Promise<void> {
  const startTime = Date.now();
  const interval = 500;

  console.log(`Waiting for ${url} to be ready...`);

  while (Date.now() - startTime < timeout) {
    let response: Response;
    try {
      response = await globalThis.fetch(url);
    } catch {
      // Network error: server not ready yet, continue waiting
      const elapsed = Date.now() - startTime;
      if (elapsed % 5000 < interval) {
        // Log every 5 seconds
        console.log(
          `  Still waiting for ${url}... (${Math.round(elapsed / 1000)}s)`,
        );
      }
      await new Promise((resolve) => setTimeout(resolve, interval));
      continue;
    }

    if (response.ok) {
      console.log(`✓ ${url} is ready`);
      return;
    }

    // Server returned an error status code (not a connection error)
    // 4xx errors (client errors) are fatal — server is up but something is misconfigured
    // 5xx errors (server errors) are transient during startup — retry
    if (response.status >= 400 && response.status < 500) {
      throw new Error(
        `Server returned ${response.status} ${response.statusText}. ` +
          `Check the server logs for details.`,
      );
    }

    // 5xx errors are transient during startup, continue waiting and retrying
    const elapsed = Date.now() - startTime;
    if (elapsed % 5000 < interval) {
      // Log every 5 seconds
      console.log(
        `  Server returned ${response.status}, retrying... (${Math.round(elapsed / 1000)}s)`,
      );
    }

    await new Promise((resolve) => setTimeout(resolve, interval));
  }

  throw new Error(`Timeout waiting for ${url} after ${timeout}ms`);
}

/**
 * Global setup for E2E tests.
 *
 * This function:
 * 1. Cleans test databases
 * 2. Checks Python virtual environment exists
 * 3. Runs database migrations (local.db and operations.db)
 * 4. Starts the Python FastAPI backend server
 * 5. Waits for backend server to be ready
 * 6. Starts the React Vite frontend dev server
 * 7. Waits for frontend server to be ready
 * 8. Stores process PIDs for teardown
 *
 * The servers will run for the entire test suite and be torn down
 * in global-teardown.ts.
 */
async function globalSetup(): Promise<void> {
  console.log("🚀 Starting E2E test environment...\n");

  // 1. Clean test databases
  console.log("🗄️  Cleaning test databases...");
  const testDbDir = path.resolve(
    __dirname,
    "../../local-server/datafiles/e2e-test",
  );
  if (fs.existsSync(testDbDir)) {
    fs.rmSync(testDbDir, { recursive: true, force: true });
  }
  fs.mkdirSync(testDbDir, { recursive: true });
  console.log("✅ Test databases cleaned\n");

  // 2. Check if virtual environment exists (before using it)
  console.log("🔧 Checking Python virtual environment...");
  const backendPath = path.resolve(__dirname, "../../local-server");
  const venvPythonPath = path.join(backendPath, ".venv/bin/python");

  if (!fs.existsSync(venvPythonPath)) {
    throw new Error(
      `Virtual environment not found at ${venvPythonPath}. ` +
        'Please run "python -m venv .venv" and "pip install -r requirements.txt" in /local-server',
    );
  }
  console.log("✅ Virtual environment found\n");

  // 3. Run database migrations
  console.log("🔄 Running database migrations...");

  try {
    const testLocalDb = path.resolve(
      backendPath,
      "datafiles/e2e-test/local.db",
    );
    const testOpsDb = path.resolve(
      backendPath,
      "datafiles/e2e-test/operations.db",
    );

    // Run local.db migrations
    console.log("  Running local.db migrations...");
    execSync(
      `${venvPythonPath} scripts/run_migrations.py local upgrade head --local-db-url sqlite:///${testLocalDb}`,
      {
        cwd: backendPath,
        stdio: "inherit",
        env: {
          ...process.env,
          PYTHONPATH: backendPath,
        },
      },
    );
    console.log("  ✓ local.db migrations completed");

    // Run operations.db migrations
    console.log("  Running operations.db migrations...");
    execSync(
      `${venvPythonPath} scripts/run_migrations.py operations upgrade head --operations-db-url sqlite:///${testOpsDb}`,
      {
        cwd: backendPath,
        stdio: "inherit",
        env: {
          ...process.env,
          PYTHONPATH: backendPath,
        },
      },
    );
    console.log("  ✓ operations.db migrations completed");

    console.log("✅ Database migrations completed\n");
  } catch (error) {
    console.error("❌ Failed to run migrations:", error);
    throw error;
  }

  // 4. Start Python backend
  console.log("🐍 Starting Python backend (port 8888)...");

  // Check if config.e2e.json exists
  const e2eConfigPath = path.join(backendPath, "config.e2e.json");
  if (!fs.existsSync(e2eConfigPath)) {
    throw new Error(
      `E2E config not found at ${e2eConfigPath}. ` +
        "Please create config.e2e.json in /local-server",
    );
  }

  console.log(`📋 Using E2E config: ${e2eConfigPath}`);

  backendProcess = spawn(venvPythonPath, ["app.py"], {
    cwd: backendPath,
    env: {
      ...process.env,
      CONFIG_PATH: e2eConfigPath,
      PYTHONUNBUFFERED: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });

  if (!backendProcess.pid) {
    throw new Error(
      "Backend process failed to spawn: no PID assigned. Check that Python is available and the virtual environment is properly set up.",
    );
  }

  console.log(
    `🔍 Backend spawned (PID: ${backendProcess.pid}) with CONFIG_PATH: ${e2eConfigPath}`,
  );

  // Log backend output
  // Set SHOW_BACKEND_LOGS=true to also see backend stdout (stderr is always logged)
  const showBackendLogs = process.env.SHOW_BACKEND_LOGS === "true";

  backendProcess.stdout?.on("data", (data) => {
    const message = data.toString().trim();
    if (message && showBackendLogs) {
      console.log(`   [Backend] ${message}`);
    }
  });

  backendProcess.stderr?.on("data", (data) => {
    const message = data.toString().trim();
    if (message) {
      // Show all stderr output: Python tracebacks, errors, warnings, CRITICAL/FATAL messages, etc.
      // This ensures startup failures and important diagnostics are never silently dropped
      console.error(`   [Backend] ${message}`);
    }
  });

  backendProcess.on("exit", (code) => {
    if (code !== null && code !== 0 && code !== 143) {
      // 143 is SIGTERM
      console.error(`❌ Backend process exited with code ${code}`);
    }
  });

  // 5. Wait for backend to be ready (60s timeout for initial NLP model loading)
  try {
    await waitForUrl("http://localhost:8888/api/v1/admin/health", 60000);
    console.log("✅ Backend ready\n");
  } catch (error) {
    console.error("❌ Backend failed to start:", error);
    if (backendProcess) {
      backendProcess.kill("SIGTERM");
    }
    throw error;
  }

  // 6. Start frontend dev server
  console.log("⚛️  Starting frontend (port 3888)...");
  const frontendPath = path.resolve(__dirname, "..");

  // Determine the npm command based on platform
  const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";

  frontendProcess = spawn(
    npmCommand,
    ["run", "dev", "--", "--port=3888", "--mode=e2e"],
    {
      cwd: frontendPath,
      env: {
        ...process.env,
        // Force Vite to use these environment variables
        VITE_API_BASE_URL: "http://localhost:8888",
        VITE_ENV: "e2e-test",
        // Ensure Vite loads .env.e2e
        MODE: "e2e",
      },
      stdio: ["ignore", "pipe", "pipe"],
      // Do not use shell: true to ensure proper child process handling
      // npm will correctly launch Vite as a child process
    },
  );

  if (!frontendProcess.pid) {
    if (backendProcess) {
      backendProcess.kill("SIGTERM");
    }
    throw new Error(
      "Frontend process failed to spawn: no PID assigned. Check that npm is available and properly configured.",
    );
  }

  // Log frontend output (Vite outputs to stderr)
  frontendProcess.stdout?.on("data", (data) => {
    const message = data.toString().trim();
    if (message && !message.includes("VITE")) {
      console.log(`   [Frontend] ${message}`);
    }
  });

  frontendProcess.stderr?.on("data", (data) => {
    const message = data.toString().trim();
    if (message) {
      // Show all stderr output to capture startup failures and important diagnostics
      console.error(`   [Frontend] ${message}`);
    }
  });

  frontendProcess.on("exit", (code) => {
    if (code !== null && code !== 0 && code !== 143) {
      console.error(`❌ Frontend process exited with code ${code}`);
    }
  });

  // 7. Wait for frontend to be ready
  try {
    await waitForUrl("http://localhost:3888", 60000);
    console.log("✅ Frontend ready\n");
  } catch (error) {
    console.error("❌ Frontend failed to start:", error);
    if (frontendProcess) {
      frontendProcess.kill("SIGTERM");
    }
    if (backendProcess) {
      backendProcess.kill("SIGTERM");
    }
    throw error;
  }

  // 8. Browser-based health check — verifies the app renders and API calls succeed through the
  // browser. A plain fetch() to each server's port passes even if the frontend serves a blank
  // error page or if CORS is misconfigured. This check catches both failure modes.
  console.log("🌐 Running browser health check...");
  const { chromium } = await import("@playwright/test");
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();

    await page.goto("http://localhost:3888", {
      waitUntil: "networkidle",
      timeout: 30000,
    });

    // Verify the page rendered actual content, not a blank error page.
    const bodyText = await page.textContent("body");
    if (!bodyText || bodyText.trim().length === 0) {
      throw new Error(
        "Frontend page rendered blank — check for build errors or missing assets",
      );
    }

    // Verify API calls succeed from the browser context. fetch() in page.evaluate() uses the
    // browser's network stack, so CORS headers and origin restrictions are enforced — a plain
    // Node fetch() call would bypass this entirely.
    const apiResult = await page.evaluate(async () => {
      try {
        const res = await fetch("http://localhost:8888/api/v1/admin/health");
        return { ok: res.ok, status: res.status };
      } catch (err) {
        return { ok: false, status: 0, error: String(err) };
      }
    });

    if (!apiResult.ok) {
      const detail =
        "error" in apiResult ? apiResult.error : `HTTP ${apiResult.status}`;
      throw new Error(
        `API call from browser context failed: ${detail}. ` +
          "This indicates a CORS misconfiguration, wrong API_BASE_URL, or proxy failure.",
      );
    }

    console.log("✅ Browser health check passed\n");
  } catch (error) {
    if (frontendProcess) frontendProcess.kill("SIGTERM");
    if (backendProcess) backendProcess.kill("SIGTERM");
    throw new Error(
      `Browser health check failed: ${error instanceof Error ? error.message : String(error)}`,
      { cause: error },
    );
  } finally {
    // Runs on both success and failure — browser is always closed.
    await browser.close();
  }

  // 9. Store process PIDs for teardown (verified to exist above)
  process.env.E2E_BACKEND_PID = backendProcess.pid!.toString();
  process.env.E2E_FRONTEND_PID = frontendProcess.pid!.toString();

  console.log("🎉 E2E environment ready!\n");
  console.log("   Frontend: http://localhost:3888");
  console.log("   Backend:  http://localhost:8888");
  console.log("");
}

export default globalSetup;
