import { useMemo } from "react";
import { SCHEMA_PROPERTIES_LIMIT, SMALL_SET_LIMIT } from "@/api/config";
import { useTaxonomyClasses } from "@/api/hooks/ontology/useClasses";
import { useTaxonomyPredicates } from "@/api/hooks/ontology/usePredicates";
import { useProperties } from "@/api/hooks/ontology/useProperties";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { buildReviewSchema, type ReviewSchema } from "./reviewSchema";

/**
 * A taxonomy's schema as the review pills read it: its classes and layers,
 * every relationship type and the predicate catalog. It shares its queries
 * with the pages that also read the classes, so nothing is fetched twice.
 */
export function useReviewSchema(taxonomyId: string): ReviewSchema {
  const { classes, isError: classesFailed } = useTaxonomyClasses(taxonomyId, !!taxonomyId);
  const { data: schemes } = useSchemes(
    taxonomyId,
    { limit: SMALL_SET_LIMIT },
    { enabled: !!taxonomyId },
  );
  const { data: propertyList, isError: propertiesFailed } = useProperties(
    undefined,
    { limit: SCHEMA_PROPERTIES_LIMIT },
    { enabled: !!taxonomyId },
  );
  const { data: catalog } = useTaxonomyPredicates(taxonomyId || undefined);
  const classesLoading = !classes && !classesFailed;
  return useMemo(
    () =>
      buildReviewSchema({
        classes: classes ?? [],
        schemes: schemes?.items ?? [],
        properties: propertyList?.items ?? [],
        predicates: catalog ?? [],
        loading: classesLoading || (!propertyList && !propertiesFailed),
      }),
    [classes, schemes, propertyList, catalog, classesLoading, propertiesFailed],
  );
}
