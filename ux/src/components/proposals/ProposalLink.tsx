import type { MouseEvent, ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { linkPath } from "@/lib/entityPaths";

interface ProposalLinkProps {
  proposalId: string;
  /** An operation to select on the proposal page. */
  operationId?: string;
  children: ReactNode;
  className?: string;
  "data-testid"?: string;
}

/** The href of a proposal's review page, optionally with one operation selected. */
export function proposalHref(proposalId: string, operationId?: string): string {
  const path = linkPath("proposal", proposalId);
  return operationId ? `${path}?op=${encodeURIComponent(operationId)}` : path;
}

/**
 * A link to a proposal's review page: a real href (so it can open in a new
 * tab) that navigates client-side on a plain click.
 */
export function ProposalLink({
  proposalId,
  operationId,
  children,
  className = "entity-link",
  "data-testid": testId,
}: ProposalLinkProps) {
  const navigate = useNavigate();

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    navigate({
      to: "/app/proposals/$proposalId",
      params: { proposalId },
      search: operationId ? { op: operationId } : {},
    });
  };

  return (
    <a
      href={proposalHref(proposalId, operationId)}
      className={className}
      onClick={handleClick}
      data-testid={testId}
    >
      {children}
    </a>
  );
}
