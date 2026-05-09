import type { ReactNode } from "react";

interface PanelProps {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Panel({ title, actions, children, className = "" }: PanelProps) {
  return (
    <div className={`panel ${className}`}>
      {title && (
        <div className="panel-head">
          <span className="panel-title">{title}</span>
          {actions}
        </div>
      )}
      <div className="panel-body">{children}</div>
    </div>
  );
}
