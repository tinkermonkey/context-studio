import { useRouterState } from "@tanstack/react-router";
import type { EntityKind } from "@/lib/entityPaths";
import type { PageContext } from "@/api/services/chat";
import { useBreadcrumbStore } from "@/stores/breadcrumbs";
import { useChatPanelStore } from "@/stores/chatPanel";
import { getBreadcrumbLabels } from "@/routes/-app-navigation";

const ENTITY_ROUTES: Array<{ pattern: RegExp; kind: EntityKind }> = [
  { pattern: /^\/app\/schema\/taxonomies\/([^/]+)$/, kind: "taxonomy" },
  { pattern: /^\/app\/schema\/schemes\/([^/]+)$/, kind: "scheme" },
  { pattern: /^\/app\/schema\/classes\/([^/]+)$/, kind: "class" },
  { pattern: /^\/app\/data\/individuals\/([^/]+)$/, kind: "individual" },
];

/** The entity an entity page's path names, if any. */
export function entityFromPath(pathname: string): { kind: EntityKind; id: string } | null {
  for (const { pattern, kind } of ENTITY_ROUTES) {
    const match = pattern.exec(pathname);
    if (match) return { kind, id: decodeURIComponent(match[1]) };
  }
  return null;
}

export interface ChatPageContext {
  /** Sent with each message; null when the user removed the chip. */
  pageContext: PageContext | null;
  /** "Viewing: X" chip label. */
  label: string;
  /** Identifies this context, so removing the chip lasts only while it applies. */
  key: string;
  dismissed: boolean;
}

/**
 * The page the user is viewing, for the chat's page context: an entity page's
 * entity (titled from "Ask about this" or the page breadcrumbs), otherwise the
 * route with its breadcrumb label.
 */
export function useChatPageContext(): ChatPageContext {
  const pathname = useRouterState().location.pathname;
  const crumbs = useBreadcrumbStore((s) => (s.pathname === pathname ? s.crumbs : null));
  const askAbout = useChatPanelStore((s) => s.askAbout);
  const dismissedKey = useChatPanelStore((s) => s.dismissedContextKey);

  const entity = entityFromPath(pathname);
  const asked = askAbout && askAbout.pathname === pathname ? askAbout : null;
  const crumbLabel = crumbs?.length
    ? crumbs[crumbs.length - 1].label
    : getBreadcrumbLabels(pathname).slice(-1)[0];

  let context: PageContext;
  let label: string;
  if (asked) {
    context = { route: pathname, entity_kind: asked.kind, entity_id: asked.id };
    label = asked.title;
  } else if (entity) {
    context = { route: pathname, entity_kind: entity.kind, entity_id: entity.id };
    label = crumbLabel || entity.id;
  } else {
    context = { route: pathname };
    label = crumbLabel || pathname;
  }
  const key = `${pathname}|${context.entity_id ?? ""}`;
  const dismissed = dismissedKey === key;
  return { pageContext: dismissed ? null : context, label, key, dismissed };
}
