import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/pipelines/")({
  component: () => (
    <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>
      Pipelines — coming soon
    </div>
  ),
});
