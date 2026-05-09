import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/schema/taxonomies")({
  component: () => <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>Taxonomies — coming soon</div>,
});
