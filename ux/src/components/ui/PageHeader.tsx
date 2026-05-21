import type { ReactNode } from "react";

interface PageHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  eyebrow: string;
  title: string;
  subtitle?: string;
  idChip?: string;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  idChip,
  actions,
  className,
  ...rest
}: PageHeaderProps) {
  return (
    <div
      data-testid="page-header"
      className={["page-header", className].filter(Boolean).join(" ")}
      {...rest}
    >
      <div className="page-header__meta">
        {eyebrow && <span className="page-header__eyebrow">{eyebrow}</span>}
        <h1 className="page-header__title">{title}</h1>
        {subtitle && <p className="page-header__subtitle">{subtitle}</p>}
        {idChip && <span className="page-header__id-chip">{idChip}</span>}
      </div>
      {actions && <div className="page-header__actions">{actions}</div>}
    </div>
  );
}
