import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";
import { initializeTracing } from "./telemetry";
import { setupRouterTelemetry } from "./telemetry/router";

// Initialize telemetry before creating the app
initializeTracing();

const router = createRouter({ routeTree });

// Set up router telemetry after router creation
setupRouterTelemetry(router);

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

const root = document.getElementById("root")!;
createRoot(root).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
