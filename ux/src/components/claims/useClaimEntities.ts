import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import { useSchemesByIds } from "@/api/hooks/ontology/useSchemes";
import { ontologyService } from "@/api/services/ontology";
import type { EntityKind } from "@/lib/entityPaths";

/** An entity a claim names, with the page it is shown on. */
export interface ClaimEntity {
  id: string;
  kind: "taxonomy" | "scheme" | "class" | "attribute" | "property";
  /** Identifier (else title) to show. */
  label: string;
  /** Title, for a tooltip. */
  title?: string;
  /**
   * The entity page to link to: its own, or for an attribute its class's and
   * for a property its source (else destination) class's, where it is listed.
   */
  page?: { kind: EntityKind; id: string };
}

/**
 * Resolve the ids a claim names: the taxonomy itself, or one of its classes,
 * property definitions, attribute definitions or concept schemes. Classes and
 * properties are looked up in one request each; ids that are neither are then
 * tried as attributes, and only those still unresolved as schemes, so an id is
 * never looked up as a kind it can't be. Unresolved (or still loading) ids are
 * absent from the map.
 */
export function useClaimEntities(
  ids: string[],
  taxonomy?: { id: string; label: string },
): Map<string, ClaimEntity> {
  const classes = useClassesByIds(ids);
  const properties = usePropertiesByIds(ids);
  // Placeholder data is the previous ids' answer (kept while paging): judging new
  // ids against it would send every one of them on to the slower lookups.
  const settled =
    classes.isSuccess &&
    properties.isSuccess &&
    !classes.isPlaceholderData &&
    !properties.isPlaceholderData;
  const leftover = useMemo(() => {
    if (!settled) return [];
    const known = new Set([
      ...(classes.data?.items ?? []).map((c) => c.id),
      ...(properties.data?.items ?? []).map((p) => p.id),
      taxonomy?.id,
    ]);
    return [...new Set(ids)].filter((id) => !known.has(id)).sort();
  }, [ids, taxonomy?.id, settled, classes.data, properties.data]);
  const attributeLookups = useQueries({
    queries: leftover.map((id) => ({
      queryKey: QUERY_KEYS.attributeDefinition(id),
      queryFn: () => ontologyService.getAttributeDefinition(id),
      staleTime: 5 * 60 * 1000,
      retry: false,
    })),
    combine: (results) => ({
      items: results.flatMap((r) => (r.data ? [r.data] : [])),
      settled: results.every((r) => !r.isPending),
    }),
  });
  const attributes = attributeLookups.items;
  const schemeIds = useMemo(() => {
    if (!attributeLookups.settled) return [];
    const found = new Set(attributes.map((a) => a.id));
    return leftover.filter((id) => !found.has(id));
  }, [leftover, attributeLookups.settled, attributes]);
  const schemes = useSchemesByIds(schemeIds);
  const { data: attributeClasses } = useClassesByIds(attributes.map((a) => a.class_id));

  return useMemo(() => {
    const entities = new Map<string, ClaimEntity>();
    if (taxonomy) {
      entities.set(taxonomy.id, {
        id: taxonomy.id,
        kind: "taxonomy",
        label: taxonomy.label,
        page: { kind: "taxonomy", id: taxonomy.id },
      });
    }
    const classLabel = new Map(
      [...(classes.data?.items ?? []), ...(attributeClasses?.items ?? [])].map((c) => [
        c.id,
        c.identifier || c.title,
      ]),
    );
    for (const c of classes.data?.items ?? []) {
      entities.set(c.id, {
        id: c.id,
        kind: "class",
        label: c.identifier || c.title,
        title: c.title,
        page: { kind: "class", id: c.id },
      });
    }
    for (const p of properties.data?.items ?? []) {
      const classId = p.domain_class_id || p.range_class_id;
      entities.set(p.id, {
        id: p.id,
        kind: "property",
        label: p.identifier || p.canonical_predicate || p.title,
        title: p.title,
        page: classId ? { kind: "class", id: classId } : undefined,
      });
    }
    for (const a of attributes) {
      // An edge attribute (#1482) has no class: it belongs to a relationship type.
      const owner = a.class_id ? classLabel.get(a.class_id) : undefined;
      entities.set(a.id, {
        id: a.id,
        kind: "attribute",
        label: owner ? `${owner}.${a.identifier}` : a.identifier,
        title: a.title,
        page: a.class_id ? { kind: "class", id: a.class_id } : undefined,
      });
    }
    for (const s of schemes) {
      entities.set(s.id, {
        id: s.id,
        kind: "scheme",
        label: s.identifier || s.title,
        title: s.title,
        page: { kind: "scheme", id: s.id },
      });
    }
    return entities;
  }, [taxonomy, classes.data, properties.data, attributes, schemes, attributeClasses]);
}
