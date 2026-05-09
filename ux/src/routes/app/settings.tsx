import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/settings")({ 
  component: () => <div style={{ color: "var(--canvas-fg-2)", fontSize: "var(--text-sm)" }}>Settings — coming soon</div>,
});
