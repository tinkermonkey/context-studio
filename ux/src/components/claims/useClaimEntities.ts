import { useMemo } from "react";
import { useAttributeDefinitionsByIds, useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import { useSchemesByIds } from "@/api/hooks/ontology/useSchemes";
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
 * tried as attributes and schemes. Unresolved (or still loading) ids are absent
 * from the map.
 */
export function useClaimEntities(
  ids: string[],
  taxonomy?: { id: string; label: string },
): Map<string, ClaimEntity> {
  const classes = useClassesByIds(ids);
  const properties = usePropertiesByIds(ids);
  const leftover = useMemo(() => {
    if (!classes.isSuccess || !properties.isSuccess) return [];
    const known = new Set([
      ...classes.data.items.map((c) => c.id),
      ...properties.data.items.map((p) => p.id),
      taxonomy?.id,
    ]);
    return ids.filter((id) => !known.has(id));
  }, [ids, taxonomy?.id, classes.isSuccess, classes.data, properties.isSuccess, properties.data]);
  const attributes = useAttributeDefinitionsByIds(leftover);
  const schemes = useSchemesByIds(leftover);
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
      const owner = classLabel.get(a.class_id);
      entities.set(a.id, {
        id: a.id,
        kind: "attribute",
        label: owner ? `${owner}.${a.identifier}` : a.identifier,
        title: a.title,
        page: { kind: "class", id: a.class_id },
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
