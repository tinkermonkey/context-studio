/**
 * The proposal's schema as the review page reads it: classes by id with their
 * labels and layers, and the relationship types (property definitions) between
 * them, inheritance-aware, for the hover overlays and the relationship editor.
 */
import type { components } from "@/api/types";
import { classLabel } from "./reviewModel";

type ClassResponse = components["schemas"]["ClassResponse"];
type SchemeResponse = components["schemas"]["ConceptSchemeResponse"];
export type PropertyDefinition = components["schemas"]["PropertyDefinitionResponse"];
type Predicate = components["schemas"]["PredicateResponse"];

export interface ReviewSchema {
  /** The classes and relationship types are still loading. */
  loading: boolean;
  classOf: (classId: string | null | undefined) => ClassResponse | undefined;
  /** A class as the reviewer reads it (its DR reference), "…" while loading, else its id. */
  classLabel: (classId: string | null | undefined) => string;
  /** The layer (concept scheme) a class is in. */
  layerOf: (classId: string | null | undefined) => string | undefined;
  property: (propertyId: string | null | undefined) => PropertyDefinition | undefined;
  /** A relationship type's predicate ("realizes"), else its identifier. */
  predicateLabel: (propertyId: string | null | undefined) => string;
  /** What a relationship type means: its description, else its predicate's. */
  predicateDefinition: (propertyId: string | null | undefined) => string | undefined;
  /** The relationship types a class (or a class it inherits from) can be the source of. */
  typesFrom: (classId: string | null | undefined) => PropertyDefinition[];
  /** The relationship types a class (or a class it inherits from) can be the target of. */
  typesTo: (classId: string | null | undefined) => PropertyDefinition[];
  /** The relationship types allowed from one class to another. */
  allowedTypes: (
    sourceClassId: string | null | undefined,
    targetClassId: string | null | undefined,
  ) => PropertyDefinition[];
  /** Whether a class is the wanted one or inherits from it; any class fits no constraint. */
  fits: (classId: string | null | undefined, wanted: string | null | undefined) => boolean;
}

/** How far a parent chain is followed (a guard against a cycle). */
const MAX_DEPTH = 50;

export function buildReviewSchema({
  classes,
  schemes,
  properties,
  predicates,
  loading,
}: {
  classes: ClassResponse[];
  schemes: SchemeResponse[];
  properties: PropertyDefinition[];
  predicates: Predicate[];
  loading: boolean;
}): ReviewSchema {
  const classById = new Map(classes.map((c) => [c.id, c]));
  const schemeById = new Map(schemes.map((s) => [s.id, s]));
  const predicateById = new Map(predicates.map((p) => [p.id, p]));
  // The relationship types between this taxonomy's classes.
  const inTaxonomy = (id: string | null | undefined) => !id || classById.has(id);
  const types = properties.filter(
    (p) =>
      (p.domain_class_id || p.range_class_id) &&
      inTaxonomy(p.domain_class_id) &&
      inTaxonomy(p.range_class_id),
  );
  const propertyById = new Map(properties.map((p) => [p.id, p]));

  const lineage = (classId: string | null | undefined): string[] => {
    const chain: string[] = [];
    let current = classId ? classById.get(classId) : undefined;
    while (current && chain.length < MAX_DEPTH && !chain.includes(current.id)) {
      chain.push(current.id);
      current = current.parent_class_id ? classById.get(current.parent_class_id) : undefined;
    }
    if (classId && chain.length === 0) chain.push(classId);
    return chain;
  };
  const fits = (classId: string | null | undefined, wanted: string | null | undefined) =>
    !wanted || lineage(classId).includes(wanted);
  const typesFrom = (classId: string | null | undefined) =>
    classId ? types.filter((p) => !!p.domain_class_id && fits(classId, p.domain_class_id)) : [];
  const typesTo = (classId: string | null | undefined) =>
    classId ? types.filter((p) => !!p.range_class_id && fits(classId, p.range_class_id)) : [];
  const predicateLabel = (propertyId: string | null | undefined) => {
    const property = propertyId ? propertyById.get(propertyId) : undefined;
    if (!property) return loading ? "…" : (propertyId ?? "?");
    const catalog = property.predicate_id ? predicateById.get(property.predicate_id) : undefined;
    return catalog?.identifier || property.canonical_predicate || property.identifier;
  };

  return {
    loading,
    classOf: (classId) => (classId ? classById.get(classId) : undefined),
    classLabel: (classId) => {
      if (!classId) return "no class";
      const found = classById.get(classId);
      if (found) return classLabel(found);
      return loading ? "…" : classId;
    },
    layerOf: (classId) => {
      const scheme = schemeById.get(classById.get(classId ?? "")?.concept_scheme_id ?? "");
      return scheme?.title;
    },
    property: (propertyId) => (propertyId ? propertyById.get(propertyId) : undefined),
    predicateLabel,
    predicateDefinition: (propertyId) => {
      const property = propertyId ? propertyById.get(propertyId) : undefined;
      if (!property) return undefined;
      const catalog = property.predicate_id ? predicateById.get(property.predicate_id) : undefined;
      return property.description || catalog?.description || undefined;
    },
    typesFrom,
    typesTo,
    allowedTypes: (sourceClassId, targetClassId) =>
      types.filter(
        (p) => fits(sourceClassId, p.domain_class_id) && fits(targetClassId, p.range_class_id),
      ),
    fits,
  };
}
