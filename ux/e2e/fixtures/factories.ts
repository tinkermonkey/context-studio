import { Page } from "@playwright/test";
import { apiRequest } from "./api-client";

/**
 * Test Data Factories for E2E Tests
 *
 * Provides typed factory functions and cleanup helpers for creating
 * and managing test data across ontology entities.
 */

let entityCounter = 0;
const testRunId = Date.now();

const getRunTimestamp = (): string => {
  entityCounter++;
  return `${testRunId}-${entityCounter}`;
};

// Type definitions (simplified - matching the API response structure)
export interface Taxonomy {
  id: string;
  title: string;
  description: string;
  version: number;
  created_at: string;
  last_modified: string;
  is_deleted?: boolean;
}

export interface ConceptScheme {
  id: string;
  title: string;
  description: string;
  taxonomy_id: string;
  version: number;
  created_at: string;
  last_modified: string;
  is_deleted?: boolean;
}

export interface OntologyClass {
  id: string;
  title: string;
  description: string;
  concept_scheme_id: string;
  taxonomy_id: string;
  parent_class_id?: string;
  version: number;
  created_at: string;
  last_modified: string;
  is_deleted?: boolean;
}

export interface PropertyDefinition {
  id: string;
  identifier: string;
  title: string;
  description: string;
  version: number;
  created_at: string;
  is_deleted?: boolean;
}

export interface Relationship {
  id: string;
  source_id: string;
  target_id: string;
  property_definition_id: string;
  created_at: string;
  is_deleted?: boolean;
}

export interface Individual {
  id: string;
  title: string;
  description?: string;
  class_ids: string[];
  version: number;
  created_at: string;
  last_modified: string;
  is_deleted?: boolean;
}

export interface DatasetMetrics {
  layers_count: number;
  domains_count: number;
  terms_count: number;
  relationships_count: number;
  individuals_count: number;
}

export interface Dataset {
  id: string;
  title: string;
  filename: string;
  description?: string;
  created_at: string;
  last_accessed: string;
  schema_version: string;
  metrics: DatasetMetrics;
  is_active: boolean;
  version: number;
}

/**
 * Create a test taxonomy
 */
export async function createTaxonomy(
  page: Page,
  overrides?: { title?: string; description?: string },
): Promise<Taxonomy> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-taxonomy-${timestamp}`;
  const description = overrides?.description || `Test taxonomy created at ${timestamp}`;

  const response = await apiRequest<Taxonomy>(page, "/api/taxonomies", {
    method: "POST",
    body: {
      title,
      description,
    },
  });

  return response;
}

/**
 * Create a test concept scheme within a taxonomy
 */
export async function createConceptScheme(
  page: Page,
  taxonomyId?: string,
  overrides?: { title?: string; description?: string },
): Promise<ConceptScheme> {
  let actualTaxonomyId = taxonomyId;

  // If no taxonomy ID provided, create one first
  if (!actualTaxonomyId) {
    const taxonomy = await createTaxonomy(page);
    actualTaxonomyId = taxonomy.id;
  }

  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-scheme-${timestamp}`;
  const description = overrides?.description || `Test scheme created at ${timestamp}`;

  const response = await apiRequest<ConceptScheme>(
    page,
    `/api/taxonomies/${actualTaxonomyId}/schemes`,
    {
      method: "POST",
      body: {
        title,
        description,
      },
    },
  );

  return response;
}

/**
 * Create a test ontology class within a scheme
 */
export async function createClass(
  page: Page,
  schemeId: string,
  overrides?: {
    title?: string;
    description?: string;
    parent_class_id?: string;
  },
): Promise<OntologyClass> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-class-${timestamp}`;
  const description = overrides?.description || `Test class definition created at ${timestamp}`;

  const body: {
    title: string;
    description: string;
    parent_class_id?: string;
  } = {
    title,
    description,
  };

  if (overrides?.parent_class_id) {
    body.parent_class_id = overrides.parent_class_id;
  }

  const response = await apiRequest<OntologyClass>(page, `/api/schemes/${schemeId}/classes`, {
    method: "POST",
    body,
  });

  return response;
}

/**
 * Create a test property definition
 */
export async function createPropertyDefinition(
  page: Page,
  overrides?: { title?: string; description?: string; identifier?: string },
): Promise<PropertyDefinition> {
  const timestamp = getRunTimestamp();
  const identifier = overrides?.identifier || `prop-${timestamp}`;
  const title = overrides?.title || `test-property-${timestamp}`;
  const description = overrides?.description || `Test property definition created at ${timestamp}`;

  const response = await apiRequest<PropertyDefinition>(page, "/api/properties", {
    method: "POST",
    body: {
      identifier,
      title,
      description,
    },
  });

  return response;
}

/**
 * Create a test relationship between two classes
 */
export async function createRelationship(
  page: Page,
  sourceClassId: string,
  targetClassId: string,
  propertyDefinitionId: string,
  relationshipType: string,
): Promise<Relationship> {
  const response = await apiRequest<Relationship>(page, "/api/relationships", {
    method: "POST",
    body: {
      source_id: sourceClassId,
      target_id: targetClassId,
      property_definition_id: propertyDefinitionId,
      relationship_type: relationshipType,
    },
  });

  return response;
}

/**
 * Create a test individual (instance) of a class
 */
export async function createIndividual(
  page: Page,
  overrides?: {
    title?: string;
    description?: string;
    class_ids?: string[];
  },
): Promise<Individual> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-individual-${timestamp}`;
  const description = overrides?.description || `Test individual created at ${timestamp}`;
  const class_ids = overrides?.class_ids || [];

  const response = await apiRequest<Individual>(page, "/api/individuals", {
    method: "POST",
    body: {
      title,
      description,
      class_ids,
    },
  });

  return response;
}

/**
 * Create a test dataset
 */
export async function createDataset(
  page: Page,
  overrides?: {
    title?: string;
    filename?: string;
    description?: string;
  },
): Promise<Dataset> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-dataset-${timestamp}`;
  const filename = overrides?.filename || `test-dataset-${timestamp}.db`;
  const description = overrides?.description || `Test dataset created at ${timestamp}`;

  const response = await apiRequest<Dataset>(page, "/api/v1/admin/datasets", {
    method: "POST",
    body: {
      title,
      filename,
      description,
    },
  });

  return response;
}

interface PaginatedResponse<T> {
  items: T[];
}

// The ontology API has no cascade delete and rejects deleting a non-empty
// parent (a taxonomy with schemes, a scheme with classes, a class with
// subclasses/individuals). So test data must be torn down children-first.
//
// Each collection is drained in repeated passes at the max page size: a pass
// deletes every currently-deletable item and re-lists; a pass that deletes
// nothing (or an empty list) stops the loop. This also clears the class
// hierarchy leaf-first without the tests needing to know its shape.
const CLEANUP_PAGE_SIZE = 1000;
const MAX_DRAIN_PASSES = 12;

async function drainCollection(page: Page, path: string): Promise<void> {
  for (let pass = 0; pass < MAX_DRAIN_PASSES; pass++) {
    let items: { id: string }[];
    try {
      const res = await apiRequest<PaginatedResponse<{ id: string }>>(
        page,
        `${path}?limit=${CLEANUP_PAGE_SIZE}`,
      );
      items = res.items ?? [];
    } catch {
      return; // endpoint unavailable — nothing to clean
    }
    if (items.length === 0) return;

    let deleted = 0;
    for (const item of items) {
      try {
        await apiRequest(page, `${path}/${item.id}`, { method: "DELETE" });
        deleted++;
      } catch {
        // Blocked (non-empty parent) or already gone — a later pass retries it
        // once its children have been removed.
      }
    }
    if (deleted === 0) return; // no progress — avoid an infinite loop
  }
}

/**
 * Delete all test-created ontology data, children-first, so every test starts
 * from a clean slate regardless of what prior tests left behind. Best-effort:
 * failures are swallowed (a test may not have created data).
 */
export async function clearTestData(page: Page): Promise<void> {
  await drainCollection(page, "/api/individuals");
  await drainCollection(page, "/api/relationships");
  await drainCollection(page, "/api/classes"); // multi-pass clears the hierarchy leaf-first
  await drainCollection(page, "/api/schemes");
  await drainCollection(page, "/api/properties");
  await drainCollection(page, "/api/taxonomies");
}

/**
 * Get individuals by class ID (for checking cascade deletion)
 */
export async function getIndividualsByClass(page: Page, classId: string): Promise<Individual[]> {
  const response = await apiRequest<PaginatedResponse<Individual>>(page, "/api/individuals", {
    method: "GET",
  });
  if (response.items) {
    return response.items.filter((ind) => ind.class_ids.includes(classId));
  }
  return [];
}
