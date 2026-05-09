import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/pipelines/runs")({
  component: () => (
    <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>
      Run History — coming soon
    </div>
  ),
});
