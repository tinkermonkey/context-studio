import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig, loadEnv } from "vite";

const isTest = !!process.env.VITEST;

/**
 * The `/api` proxy goes to the same back end as the API client:
 * VITE_API_BASE_URL (from the environment or the mode's .env file), else :8000.
 * A second instance (./dev.sh --worktree, the E2E stack) sets it, so its proxy
 * never reaches the main back end on :8000.
 */
function apiProxyTarget(mode: string): string {
  const baseUrl = loadEnv(mode, __dirname, "VITE_").VITE_API_BASE_URL;
  if (!baseUrl) return "http://127.0.0.1:8000";
  const url = new URL(baseUrl);
  // The back end listens on 127.0.0.1; "localhost" may resolve to ::1 first.
  if (url.hostname === "localhost") url.hostname = "127.0.0.1";
  return url.origin;
}

export default defineConfig(({ mode }) => ({
  server: {
    // No `host`: Vite's default (localhost) keeps the dev server, `vite preview`
    // and their /api proxy reachable from this machine only. `host: true` would
    // let any machine on the network call the unauthenticated REST API through
    // the proxy (#1655). vite.config.test.ts pins this.
    port: 3100,
    proxy: {
      "/api": {
        target: apiProxyTarget(mode),
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime"],
  },
  plugins: [
    !isTest &&
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
      }),
    react(),
    tailwindcss(),
  ],
}));
