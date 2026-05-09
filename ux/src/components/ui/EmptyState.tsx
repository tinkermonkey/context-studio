import { type ReactNode } from "react";
import { Button } from "./Button";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  variant?: "default" | "compact";
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  variant = "default",
}: EmptyStateProps) {
  const padding = variant === "compact" ? "var(--space-8)" : "var(--space-12)";

  return (
    <div
      className="empty-state"
      style={{
        padding,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "var(--space-4)",
        minHeight: "200px",
      }}
      data-testid="empty-state"
    >
      {icon && (
        <div style={{ color: "var(--canvas-fg-3)", display: "flex" }}>
          {icon}
        </div>
      )}
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            fontWeight: 500,
            color: "var(--canvas-fg)",
            fontSize: "var(--text-sm)",
            marginBottom: "var(--space-2)",
          }}
        >
          {title}
        </div>
        {description && (
          <div
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--canvas-fg-3)",
              lineHeight: 1.5,
            }}
          >
            {description}
          </div>
        )}
      </div>
      {action && (
        <Button
          variant="primary"
          size="sm"
          onClick={action.onClick}
          data-testid="empty-state-action"
          style={{ marginTop: "var(--space-2)" }}
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}
