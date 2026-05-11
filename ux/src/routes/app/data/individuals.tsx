import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/data/individuals")({
  component: () => (
    <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>
      Individuals — coming soon
    </div>
  ),
});
