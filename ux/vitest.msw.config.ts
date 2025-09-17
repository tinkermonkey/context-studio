import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.msw.setup.ts",
    globals: true,
    coverage: {
      provider: "istanbul",
    },
    exclude: ["node_modules", "dist"],
    // Only run MSW integration tests
    include: ["test/integration/example.test.tsx", "test/integration/msw_*.test.*"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});