import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/pipelines/flavors")({ 
  component: () => <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>Flavors — coming soon</div>,
});
