import type { ReactNode, HTMLAttributes } from "react";
import { StatGrid as HeimdallStatGrid } from "@tinkermonkey/heimdall-ui";

interface StatGridProps extends HTMLAttributes<HTMLDivElement> {
  columns?: number;
  children: ReactNode;
}

export function StatGrid({ columns, children, ...rest }: StatGridProps) {
  return (
    <HeimdallStatGrid columns={columns} {...rest}>
      {children}
    </HeimdallStatGrid>
  );
}
