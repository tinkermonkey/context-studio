import { useTaxonomies } from "./useTaxonomies";
import { useSchemes } from "./useSchemes";
import { useClasses } from "./useClasses";
import { useIndividuals } from "./useIndividuals";
import { useProperties } from "./useProperties";
import { useRelationships } from "./useRelationships";

/** A one-row request: only the response `total` is read. */
const COUNT_PARAMS = { limit: 1 } as const;

export interface EntityCounts {
  taxonomies?: number;
  schemes?: number;
  classes?: number;
  individuals?: number;
  properties?: number;
  relationships?: number;
}

/**
 * Unfiltered totals for every ontology collection, for tab and sidebar counts
 * (`schemaOnly` skips individuals).
 * Each is a `limit=1` request that reads the server's `total`; mutations
 * invalidate the collection's root key, so the counts stay current.
 */
export function useEntityCounts(options?: { schemaOnly?: boolean }): EntityCounts {
  const taxonomies = useTaxonomies(COUNT_PARAMS);
  const schemes = useSchemes(undefined, COUNT_PARAMS);
  const classes = useClasses(COUNT_PARAMS);
  // Schema tabs show no individual count, so they skip that request.
  const individuals = useIndividuals(COUNT_PARAMS, { enabled: !options?.schemaOnly });
  const properties = useProperties(undefined, COUNT_PARAMS);
  const relationships = useRelationships(COUNT_PARAMS);
  return {
    taxonomies: taxonomies.data?.total,
    schemes: schemes.data?.total,
    classes: classes.data?.total,
    individuals: individuals.data?.total,
    properties: properties.data?.total,
    relationships: relationships.data?.total,
  };
}
