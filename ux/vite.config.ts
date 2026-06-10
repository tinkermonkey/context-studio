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
      // v0.3.0 markers
      const startMarker = "var ze = { exports: {} }, be = {};";
      const endMarker = "var e = ze.exports;";
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
      // v0.3.0-current markers (Ze/ye) — also injects React global for forwardRef/createContext
      const startMarker2 = "var Ze = { exports: {} }, ye = {};";
      const endMarker2 = "var e = Ze.exports;";
      const startIdx2 = code.indexOf(startMarker2);
      const endIdx2 = code.indexOf(endMarker2);
      if (startIdx2 !== -1 && endIdx2 !== -1) {
        return (
          'import React from "react";\nimport { jsx as __h_jsx, jsxs as __h_jsxs, Fragment as __h_Fragment } from "react/jsx-runtime";\n' +
          code.slice(0, startIdx2) +
          "var e = { jsx: __h_jsx, jsxs: __h_jsxs, Fragment: __h_Fragment };" +
          code.slice(endIdx2 + endMarker2.length)
        );
      }
      // v0.2.0 fallback markers (Se/je)
      const startMarker3 = "var Se = { exports: {} }, je = {};";
      const endMarker3 = "var e = Se.exports;";
      const startIdx3 = code.indexOf(startMarker3);
      const endIdx3 = code.indexOf(endMarker3);
      if (startIdx3 !== -1 && endIdx3 !== -1) {
        return (
          'import { jsx as __h_jsx, jsxs as __h_jsxs, Fragment as __h_Fragment } from "react/jsx-runtime";\n' +
          code.slice(0, startIdx3) +
          "var e = { jsx: __h_jsx, jsxs: __h_jsxs, Fragment: __h_Fragment };" +
          code.slice(endIdx3 + endMarker3.length)
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
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
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
