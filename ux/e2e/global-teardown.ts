import { execSync } from "child_process";

/**
 * Kill a process by PID, handling both Unix and Windows platforms.
 */
function killProcess(pid: number): void {
  try {
    if (process.platform === "win32") {
      // Windows: Use taskkill
      execSync(`taskkill /pid ${pid} /T /F`, {
        stdio: "ignore",
      });
    } else {
      // Unix: Send SIGTERM, then SIGKILL if needed
      process.kill(pid, "SIGTERM");

      // Wait a bit, then force kill if still running
      setTimeout(() => {
        try {
          process.kill(pid, 0); // Check if process exists
          process.kill(pid, "SIGKILL"); // Force kill
        } catch (error) {
          // Only ignore ESRCH (process doesn't exist)
          // Report other errors like EPERM (permission denied)
          const err = error as NodeJS.ErrnoException;
          if (err.code !== "ESRCH") {
            console.error(
              `⚠️  Warning: Failed to kill process ${pid}: ${err.code} - ${err.message}`,
            );
          }
        }
      }, 2000);
    }
  } catch (error) {
    // Report errors when killing the process
    const err = error as NodeJS.ErrnoException;
    if (err.code === "ESRCH") {
      // Process not found is expected and fine
      return;
    }
    console.error(
      `⚠️  Warning: Failed to kill process ${pid}: ${err.code || "unknown error"} - ${err.message || String(error)}`,
    );
  }
}

/**
 * Global teardown for E2E tests.
 *
 * This function:
 * 1. Stops the frontend dev server
 * 2. Stops the Python backend server
 * 3. Optionally cleans up test databases
 *
 * Processes are killed gracefully with SIGTERM, falling back to SIGKILL
 * if they don't respond.
 */
async function globalTeardown(): Promise<void> {
  console.log("\n🧹 Shutting down E2E test environment...\n");

  // Kill frontend process
  const frontendPid = process.env.E2E_FRONTEND_PID;
  if (frontendPid) {
    console.log("⚛️  Stopping frontend...");
    killProcess(parseInt(frontendPid, 10));
    console.log("✅ Frontend stopped");
  }

  // Kill backend process
  const backendPid = process.env.E2E_BACKEND_PID;
  if (backendPid) {
    console.log("🐍 Stopping backend...");
    killProcess(parseInt(backendPid, 10));
    console.log("✅ Backend stopped");
  }

  // Wait a moment for processes to clean up
  await new Promise((resolve) => setTimeout(resolve, 1000));

  // Optional: Clean test databases
  // Uncomment if you want to remove test data after each run
  // const testDbDir = path.resolve(__dirname, '../../local-server/datafiles/e2e-test');
  // if (fs.existsSync(testDbDir)) {
  //   fs.rmSync(testDbDir, { recursive: true, force: true });
  //   console.log('✅ Test databases cleaned');
  // }

  console.log("\n🎉 E2E environment shutdown complete!\n");
}

export default globalTeardown;
