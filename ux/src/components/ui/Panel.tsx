import type { ReactNode, HTMLAttributes } from "react";
import { Panel as HeimdallPanel } from "@tinkermonkey/heimdall-ui";

interface PanelProps extends HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  footer?: ReactNode;
  bordered?: boolean;
  children: ReactNode;
}

export function Panel({
  title,
  subtitle,
  actions,
  footer,
  bordered,
  children,
  className,
  ...rest
}: PanelProps) {
  if (actions) {
    return (
      <div className={className} {...rest}>
        <HeimdallPanel
          title={title}
          subtitle={subtitle}
          footer={
            <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
              <div />
              <div>{actions}</div>
            </div>
          }
          bordered={bordered}
        >
          {children}
        </HeimdallPanel>
      </div>
    );
  }

  return (
    <HeimdallPanel
      title={title}
      subtitle={subtitle}
      footer={footer}
      bordered={bordered}
      className={className}
      {...rest}
    >
      {children}
    </HeimdallPanel>
  );
}
