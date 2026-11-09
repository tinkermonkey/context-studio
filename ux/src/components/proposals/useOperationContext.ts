import { useMemo } from "react";
import { useAttributeDefinitionsByIds, useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { useIndividualsByIds } from "@/api/hooks/ontology/useIndividuals";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import { useTaxonomiesByIds } from "@/api/hooks/ontology/useTaxonomies";
import type { ProposedOperation } from "@/api/services/proposals";
import type { components } from "@/api/types";
import {
  namedEntityIds,
  referencedClassIds,
  referencedPropertyIds,
  resolveRef,
  type RefMap,
  type TripleEnd,
  type TripleSource,
} from "./proposalModel";

type AttributeDefinition = components["schemas"]["AttributeDefinitionResponse"];

/**
 * What rendering an operation needs from the workspace: class labels, current
 * properties, and names for the attributes, individuals and taxonomies it names by id.
 */
export interface OperationContext {
  /**
   * An end's label for this operation: a class's identifier (or title), a
   * "$ref" create's title, "any" for an unconstrained end, and for an unknown
   * one "…" while loading, "deleted" when the target property is gone, "?"
   * otherwise.
   */
  endLabel: (end: TripleEnd, operation: ProposedOperation) => string;
  /** A class end's title, for a tooltip. */
  endTitle: (end: TripleEnd, operation: ProposedOperation) => string | undefined;
  /** The current property definition an update or delete targets, once loaded. */
  currentProperty: (id: string | null | undefined) => TripleSource | undefined;
  /** True when a property operation's target is known to be gone (the lookup found none). */
  targetGone: (operation: ProposedOperation) => boolean;
  /** The current attribute definition an attribute update or delete targets, once loaded. */
  attribute: (id: string | null | undefined) => AttributeDefinition | undefined;
  /**
   * A title for an id the operation names: a "$ref" create's, or a class's,
   * individual's or taxonomy's once loaded; undefined when unknown.
   */
  nameOf: (id: string | null | undefined, operation: ProposedOperation) => string | undefined;
  /** A property definition's predicate (else identifier), once loaded. */
  predicateOf: (id: string | null | undefined) => string | undefined;
}

type PropertyList = ReturnType<typeof usePropertiesByIds>;

/**
 * Resolve the classes and target properties the operations refer to, one
 * query each. `refs` maps each operation id to its proposal's "$ref" creates.
 * Pass `targets` when the caller already queried the target properties.
 */
export function useOperationContext(
  operations: ProposedOperation[],
  refs?: Map<string, RefMap>,
  targets?: PropertyList,
): OperationContext {
  const propertyIds = useMemo(
    () => (targets ? [] : referencedPropertyIds(operations)),
    [operations, targets],
  );
  const ownTargets = usePropertiesByIds(propertyIds);
  const properties = targets ?? ownTargets;
  const propertyItems = properties.data?.items;

  // An update's untouched ends come from the current property, so look those classes up too.
  const classIds = useMemo(
    () => [
      ...operations.flatMap((op) => referencedClassIds(op, refs?.get(op.id))),
      ...(propertyItems ?? []).flatMap((p) => [p.domain_class_id, p.range_class_id]),
    ],
    [operations, refs, propertyItems],
  );
  // Attributes, individuals, taxonomies and relationship types named by id.
  const named = useMemo(
    () => namedEntityIds(operations, (op) => refs?.get(op.id)),
    [operations, refs],
  );
  const attributes = useAttributeDefinitionsByIds(named.attributes);
  const { data: individuals } = useIndividualsByIds(named.individuals);
  const taxonomies = useTaxonomiesByIds(named.taxonomies);
  const { data: predicates } = usePropertiesByIds(named.properties);
  const { data: classes } = useClassesByIds([
    ...classIds,
    ...named.classes,
    ...attributes.map((a) => a.class_id),
  ]);
  const propertiesLoaded = properties.isSuccess;
  const propertiesFailed = properties.isError;

  return useMemo(() => {
    const classById = new Map((classes?.items ?? []).map((c) => [c.id, c]));
    const propertyById = new Map((propertyItems ?? []).map((p) => [p.id, p]));
    const attributeById = new Map(attributes.map((a) => [a.id, a]));
    const predicateById = new Map((predicates?.items ?? []).map((p) => [p.id, p]));
    const titles = new Map<string, string>([
      ...(individuals?.items ?? []).map((i) => [i.id, i.title] as const),
      ...taxonomies.map((t) => [t.id, t.title] as const),
      ...(classes?.items ?? []).map((c) => [c.id, c.title || c.identifier] as const),
    ]);
    const unknownLabel = (operation: ProposedOperation) => {
      if (!operation.target_id || propertiesFailed) return "?";
      if (!propertiesLoaded) return operation.stale ? "deleted" : "…";
      return propertyById.has(operation.target_id) ? "?" : "deleted";
    };
    return {
      endLabel: (end, operation) => {
        if (end === null) return "any";
        if (end === undefined) return unknownLabel(operation);
        const opRefs = refs?.get(operation.id);
        const id = resolveRef(end, opRefs);
        if (id.startsWith("$")) return opRefs?.get(id)?.title ?? id;
        const found = classById.get(id);
        return found?.identifier || found?.title || opRefs?.get(end)?.title || id;
      },
      endTitle: (end, operation) =>
        end ? classById.get(resolveRef(end, refs?.get(operation.id)))?.title : undefined,
      currentProperty: (id) => (id ? propertyById.get(id) : undefined),
      targetGone: (operation) =>
        operation.kind === "property" &&
        !!operation.target_id &&
        propertiesLoaded &&
        !propertyById.has(operation.target_id),
      attribute: (id) => (id ? attributeById.get(id) : undefined),
      nameOf: (id, operation) => {
        if (!id) return undefined;
        const opRefs = refs?.get(operation.id);
        const resolved = resolveRef(id, opRefs);
        return titles.get(resolved) ?? opRefs?.get(id)?.title;
      },
      predicateOf: (id) => {
        const property = id ? predicateById.get(id) : undefined;
        return property ? property.canonical_predicate || property.identifier : undefined;
      },
    };
  }, [
    classes,
    propertyItems,
    refs,
    propertiesLoaded,
    propertiesFailed,
    attributes,
    individuals,
    taxonomies,
    predicates,
  ]);
}
