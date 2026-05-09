import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/schema/schemes")({
  component: () => (
    <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>
      Concept Schemes — coming soon
    </div>
  ),
});
