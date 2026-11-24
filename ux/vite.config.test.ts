import type { UserConfig, UserConfigFnObject } from "vite";
import { describe, expect, it, vi } from "vitest";

// Loading the real Vite and its plugins under jsdom trips esbuild's TextEncoder
// check, and only the config object matters here.
vi.mock("vite", () => ({
  defineConfig: (config: unknown) => config,
  loadEnv: () => ({}),
}));
vi.mock("@tailwindcss/vite", () => ({ default: () => "tailwind" }));
vi.mock("@tanstack/router-plugin/vite", () => ({ tanstackRouter: () => "router" }));
vi.mock("@vitejs/plugin-react", () => ({ default: () => "react" }));

import viteConfig from "./vite.config";

const LAN_HOSTS = [true, "0.0.0.0", "::", "::0"];

function resolveConfig(mode: string): UserConfig {
  return (viteConfig as unknown as UserConfigFnObject)({
    command: "serve",
    mode,
    isSsrBuild: false,
    isPreview: false,
  });
}

describe("vite.config", () => {
  it.each(["development", "e2e", "production"])(
    "does not open the dev server or preview to the network (mode %s)",
    (mode) => {
      const config = resolveConfig(mode);

      for (const host of LAN_HOSTS) {
        expect(config.server?.host).not.toBe(host);
        expect(config.preview?.host).not.toBe(host);
      }
      // Unset means Vite's default, localhost; `vite preview` inherits server.host.
      expect(config.server?.host).toBeUndefined();
      expect(config.preview?.host).toBeUndefined();
    },
  );

  it("still proxies /api to the back end", () => {
    const proxy = resolveConfig("development").server?.proxy as Record<string, { target: string }>;

    expect(proxy["/api"].target).toBe("http://127.0.0.1:8000");
  });
});
