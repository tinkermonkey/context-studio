import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";

interface SourcesPageLinkProps {
  /** The source's taxonomy: the Sources page opens filtered to it. */
  taxonomyId: string;
  children: ReactNode;
  className?: string;
  "data-testid"?: string;
}

/**
 * A source's title as a link to Data › Sources for its taxonomy. Sources have
 * no page of their own (only the extract page), so this is where one is found.
 */
export function SourcesPageLink({
  taxonomyId,
  children,
  className = "entity-link",
  "data-testid": testId,
}: SourcesPageLinkProps) {
  return (
    <Link
      to="/app/data/sources"
      search={{ taxonomy: taxonomyId }}
      className={className}
      data-testid={testId}
    >
      {children}
    </Link>
  );
}
