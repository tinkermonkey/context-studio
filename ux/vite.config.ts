import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import type { Plugin } from "vite";
import { defineConfig } from "vite";

// Heimdall bundles an inline React 18 jsx-runtime which React 19 rejects.
// This plugin replaces the entire inline block with a real import from react/jsx-runtime.
function heimdallReact19Compat(): Plugin {
  return {
    name: "heimdall-react19-compat",
    transform(code, id) {
      if (!id.includes("heimdall-ui")) return;
      const startMarker = "var me = { exports: {} }, J = {};";
      const endMarker = "var a = me.exports;";
      const startIdx = code.indexOf(startMarker);
      const endIdx = code.indexOf(endMarker);
      if (startIdx === -1 || endIdx === -1) return;
      return (
        'import { jsx as __h_jsx, jsxs as __h_jsxs, Fragment as __h_Fragment } from "react/jsx-runtime";\n' +
        code.slice(0, startIdx) +
        "var a = { jsx: __h_jsx, jsxs: __h_jsxs, Fragment: __h_Fragment };" +
        code.slice(endIdx + endMarker.length)
      );
    },
  };
}

const isTest = !!process.env.VITEST;

export default defineConfig({
  server: {
    host: true,
    port: 3100,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime"],
  },
  optimizeDeps: {
    exclude: ["@tinkermonkey/heimdall-ui"],
  },
  plugins: [
    heimdallReact19Compat(),
    !isTest &&
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
      }),
    react(),
    tailwindcss(),
  ],
});
