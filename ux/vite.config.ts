import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import flowbiteReact from "flowbite-react/plugin/vite";
import path from "path";

// https://vitejs.dev/config/
const isTest = !!process.env.VITEST;

export default defineConfig({
  server: {
    host: true, // Listen on all network interfaces
    port: 3100,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  plugins: [
    // don't enable the router plugin during unit tests; it installs a code-splitting
    // transform that conflicts with Vitest's virtual module handling
    !isTest &&
      tanstackRouter({
        target: "react",
        autoCodeSplitting: true,
      }),
    react(),
    tailwindcss(),
    flowbiteReact(),
  ],
});
