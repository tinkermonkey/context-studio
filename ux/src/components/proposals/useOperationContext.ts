import { useMemo } from "react";
import { useClassesByIds } from "@/api/hooks/ontology/useClasses";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import type { ProposedOperation } from "@/api/services/proposals";
import { referencedClassIds, referencedPropertyIds, type TripleSource } from "./proposalModel";

/** What rendering an operation needs from the workspace: class labels and current properties. */
export interface OperationContext {
  /** A class id's identifier (or title); "$ref" and unknown ids come back as given. */
  classLabel: (id: string | undefined) => string;
  /** A class id's title, for a tooltip. */
  classTitle: (id: string | undefined) => string | undefined;
  /** The current property definition an update or delete targets, once loaded. */
  currentProperty: (id: string | null | undefined) => TripleSource | undefined;
}

/**
 * Resolve the class ids and target properties the operations refer to, in one
 * query each.
 */
export function useOperationContext(operations: ProposedOperation[]): OperationContext {
  const propertyIds = useMemo(() => referencedPropertyIds(operations), [operations]);
  const { data: properties } = usePropertiesByIds(propertyIds);
  // An update's untouched ends come from the current property, so look those classes up too.
  const classIds = useMemo(
    () => [
      ...operations.flatMap(referencedClassIds),
      ...(properties?.items ?? []).flatMap((p) => [p.domain_class_id, p.range_class_id]),
    ],
    [operations, properties],
  );
  const { data: classes } = useClassesByIds(classIds);

  return useMemo(() => {
    const classById = new Map((classes?.items ?? []).map((c) => [c.id, c]));
    const propertyById = new Map((properties?.items ?? []).map((p) => [p.id, p]));
    return {
      classLabel: (id) => {
        if (!id) return "any";
        const found = classById.get(id);
        return found?.identifier || found?.title || id;
      },
      classTitle: (id) => (id ? classById.get(id)?.title : undefined),
      currentProperty: (id) => (id ? propertyById.get(id) : undefined),
    };
  }, [classes, properties]);
}
