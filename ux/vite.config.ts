import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { defineConfig } from "vite";

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
  plugins: [
    !isTest &&
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
      }),
    react(),
    tailwindcss(),
  ],
});
