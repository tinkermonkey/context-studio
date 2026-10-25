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
