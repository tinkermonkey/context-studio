import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";

interface SourcesPageLinkProps {
  /** The source's taxonomy: the Sources page opens filtered to it. */
  taxonomyId: string;
  children: ReactNode;
  /**
   * Open in a new tab, so the page it is on keeps its state (e.g. a reviewer's
   * unsent decision and reason on a proposal).
   */
  newTab?: boolean;
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
  newTab = false,
  className = "entity-link",
  "data-testid": testId,
}: SourcesPageLinkProps) {
  return (
    <Link
      to="/app/data/sources"
      search={{ taxonomy: taxonomyId }}
      className={className}
      data-testid={testId}
      {...(newTab ? { target: "_blank", rel: "noopener noreferrer" } : {})}
    >
      {children}
      {newTab && <span className="sr-only"> (opens in a new tab)</span>}
    </Link>
  );
}
