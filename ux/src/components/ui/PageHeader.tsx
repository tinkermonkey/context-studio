import type { ReactNode } from "react";
import { PageHeader as HeimdallPageHeader } from "@tinkermonkey/heimdall-ui";

interface PageHeaderProps {
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
}: PageHeaderProps) {
  return (
    <HeimdallPageHeader
      eyebrow={eyebrow}
      title={title}
      subtitle={subtitle}
      idChip={idChip}
      actions={actions}
      className={className}
      data-testid="page-header"
      role="banner"
    />
  );
}
