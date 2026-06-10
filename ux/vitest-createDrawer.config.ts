import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    globals: true,
    pool: "vmForks",
    execArgv: ["--max-old-space-size=8192"],
    env: {
      NODE_OPTIONS: "--max-old-space-size=8192",
    },
    include: ["src/components/crud/__tests__/CreateDrawer.test.tsx"],
    exclude: ["node_modules", "dist", "e2e/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
