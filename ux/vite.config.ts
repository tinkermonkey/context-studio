import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import type { Plugin } from "vite";
import { defineConfig } from "vite";

// Heimdall bundles an inline React jsx-runtime which causes a duplicate React
// instance error. This plugin replaces the inline block with a real import.
function heimdallReact19Compat(): Plugin {
  return {
    name: "heimdall-react19-compat",
    transform(code, id) {
      if (!id.includes("heimdall-ui")) return;
      // v0.2.0 markers
      const startMarker = "var Se = { exports: {} }, je = {};";
      const endMarker = "var e = Se.exports;";
      const startIdx = code.indexOf(startMarker);
      const endIdx = code.indexOf(endMarker);
      if (startIdx !== -1 && endIdx !== -1) {
        return (
          'import { jsx as __h_jsx, jsxs as __h_jsxs, Fragment as __h_Fragment } from "react/jsx-runtime";\n' +
          code.slice(0, startIdx) +
          "var e = { jsx: __h_jsx, jsxs: __h_jsxs, Fragment: __h_Fragment };" +
          code.slice(endIdx + endMarker.length)
        );
      }
      // v0.1.x fallback markers
      const startMarker2 = "var me = { exports: {} }, J = {};";
      const endMarker2 = "var a = me.exports;";
      const startIdx2 = code.indexOf(startMarker2);
      const endIdx2 = code.indexOf(endMarker2);
      if (startIdx2 !== -1 && endIdx2 !== -1) {
        return (
          'import { jsx as __h_jsx, jsxs as __h_jsxs, Fragment as __h_Fragment } from "react/jsx-runtime";\n' +
          code.slice(0, startIdx2) +
          "var a = { jsx: __h_jsx, jsxs: __h_jsxs, Fragment: __h_Fragment };" +
          code.slice(endIdx2 + endMarker2.length)
        );
      }
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
