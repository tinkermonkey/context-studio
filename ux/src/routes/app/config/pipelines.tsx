import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/config/pipelines")({
  // Pathless route - no component needed for flat routing
  // Child routes are self-contained and don't need parent outlet
});
