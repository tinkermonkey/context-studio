type BadgeColor = StatusColor;

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  color?: BadgeColor;
  pulse?: boolean;
}

interface StatusBadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  color?: BadgeColor;
  pulse?: boolean;
}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ color = "cyan", pulse = false, className = "", ...props }, ref) => {
    const classNames = ["badge", `badge--${color}`, pulse && "badge--pulse", className]
      .filter(Boolean)
      .join(" ");

    return <span ref={ref} className={classNames} {...props} />;
  },
);

Badge.displayName = "Badge";

const StatusBadge = React.forwardRef<HTMLDivElement, StatusBadgeProps>(
  ({ color = "cyan", pulse = false, className = "", role = "img", ...props }, ref) => {
    const classNames = [
      "status-badge",
      `status-badge--${color}`,
      pulse && "status-badge--pulse",
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return <div ref={ref} role={role} className={classNames} {...props} />;
  },
);

StatusBadge.displayName = "StatusBadge";

// --- Babel-standalone: expose runtime values to window ---
window.Badge = Badge;
window.StatusBadge = StatusBadge;
