import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/schema/relationships")({
  component: () => (
    <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>
      Relationships — coming soon
    </div>
  ),
});
