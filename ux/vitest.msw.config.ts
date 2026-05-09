import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: "./vitest.msw.setup.ts",
    globals: true,
    coverage: {
      provider: "istanbul",
    },
    exclude: ["node_modules", "dist", "e2e/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
      "@/vitest.msw.setup": path.resolve(__dirname, "vitest.msw.setup.ts"),
    },
  },
});
