import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/reference/sources")({ 
  component: () => <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>Sources — coming soon</div>,
});
