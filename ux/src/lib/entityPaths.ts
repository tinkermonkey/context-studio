/** Kinds of ontology entity that have their own page. */
export type EntityKind = "taxonomy" | "scheme" | "class" | "individual";

const ENTITY_PAGE_PREFIX: Record<EntityKind, string> = {
  taxonomy: "/app/schema/taxonomies",
  scheme: "/app/schema/schemes",
  class: "/app/schema/classes",
  individual: "/app/data/individuals",
};

/** The page path for one taxonomy, concept scheme, class or individual. */
export function entityPath(kind: EntityKind, id: string): string {
  return `${ENTITY_PAGE_PREFIX[kind]}/${encodeURIComponent(id)}`;
}

/** A change proposal's review page is PROPOSAL_PAGE_PREFIX/<id>. */
export const PROPOSAL_PAGE_PREFIX = "/app/proposals";

/** What chat answers can link to: an entity page or a proposal's review page. */
export type LinkKind = EntityKind | "proposal";

/** The page path for a chat link target. */
export function linkPath(kind: LinkKind, id: string): string {
  if (kind === "proposal") return `${PROPOSAL_PAGE_PREFIX}/${encodeURIComponent(id)}`;
  return entityPath(kind, id);
}
