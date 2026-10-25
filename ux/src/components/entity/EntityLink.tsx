import type { MouseEvent, ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { entityPath, type EntityKind } from "@/lib/entityPaths";

interface EntityLinkProps {
  kind: EntityKind;
  id: string;
  children: ReactNode;
  className?: string;
  "data-testid"?: string;
}

/**
 * A link to an entity page: a real href (so it can open in a new tab) that
 * navigates client-side on a plain click.
 */
export function EntityLink({
  kind,
  id,
  children,
  className = "entity-link",
  "data-testid": testId,
}: EntityLinkProps) {
  const navigate = useNavigate();
  const href = entityPath(kind, id);

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    navigate({ to: href });
  };

  return (
    <a href={href} className={className} onClick={handleClick} data-testid={testId}>
      {children}
    </a>
  );
}
