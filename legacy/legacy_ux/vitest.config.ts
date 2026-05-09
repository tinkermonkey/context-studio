import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.setup.ts",
    globals: true,
    coverage: {
      provider: "istanbul",
    },
    exclude: [
      "node_modules",
      "dist",
      "test/integration/example.test.tsx",
      "test/integration/msw_*.test.*",
      "e2e/**",
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
});
