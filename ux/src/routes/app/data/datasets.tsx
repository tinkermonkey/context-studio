import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/data/datasets")({ 
  component: () => <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>Datasets — coming soon</div>,
});
