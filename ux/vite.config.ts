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
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
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
