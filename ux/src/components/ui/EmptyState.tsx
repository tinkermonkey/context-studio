import { type ReactNode } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string | ReactNode;
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
  return (
    <div
      className={variant === "compact" ? "empty-state compact" : "empty-state"}
      data-testid="empty-state"
    >
      {icon && <div className="empty-state-icon">{icon}</div>}
      <div className="empty-state-content">
        <div className="empty-state-title">{title}</div>
        {description && <div className="empty-state-description">{description}</div>}
      </div>
      {action && (
        <Button
          variant="primary"
          size="sm"
          onClick={action.onClick}
          data-testid="empty-state-action"
          className="empty-state-action"
        >
          {action.label}
        </Button>
      )}
    </div>
  );
}
