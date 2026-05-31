type FormCalloutVariant = "info" | "warn" | "error";

interface FormCalloutProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: FormCalloutVariant;
  icon?: IconName;
  children: React.ReactNode;
}

const parseBody = (text: string): React.ReactNode[] => {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;

  const regex = /`([^`]+)`/g;
  let match;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }
    parts.push(
      <code key={`code-${match.index}`} className="form-callout__code">
        {match[1]}
      </code>,
    );
    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length > 0 ? parts : [text];
};

const FormCallout = React.forwardRef<HTMLDivElement, FormCalloutProps>(
  ({ variant = "info", icon, children, className = "", role, ...props }, ref) => {
    const parsedBody = typeof children === "string" ? parseBody(children) : children;
    const resolvedRole = role ?? (variant === "error" || variant === "warn" ? "alert" : "note");

    return (
      <div
        ref={ref}
        className={["form-callout", `form-callout--${variant}`, className]
          .filter(Boolean)
          .join(" ")}
        data-testid="form-callout"
        role={resolvedRole}
        {...props}
      >
        {icon && (
          <div className="form-callout__icon">
            <Icon name={icon} size={16} />
          </div>
        )}
        <div className="form-callout__body">{parsedBody}</div>
      </div>
    );
  },
);

FormCallout.displayName = "FormCallout";

// --- Babel-standalone: expose runtime values to window ---
window.FormCallout = FormCallout;
