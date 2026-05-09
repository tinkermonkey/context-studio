import { Page } from "@playwright/test";
import { apiRequest } from "./api-client";

/**
 * Test Data Factories for E2E Tests
 *
 * Provides typed factory functions and cleanup helpers for creating
 * and managing test data across ontology entities.
 */

let entityCounter = 0;

const getRunTimestamp = (): string => {
  entityCounter++;
  const timestamp = Date.now();
  return `${timestamp}-${entityCounter}`;
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
): Promise<Relationship> {
  const response = await apiRequest<Relationship>(page, "/api/relationships", {
    method: "POST",
    body: {
      source_id: sourceClassId,
      target_id: targetClassId,
      property_definition_id: propertyDefinitionId,
    },
  });

  return response;
}

interface PaginatedResponse<T> {
  items: T[];
}

/**
 * Clear all test data by deleting all non-default entities
 * This is a simple implementation that calls delete endpoints
 */
export async function clearTestData(page: Page): Promise<void> {
  try {
    // Delete all relationships first
    const relationshipsResponse = await apiRequest<PaginatedResponse<Relationship>>(
      page,
      "/api/relationships",
    );
    if (relationshipsResponse.items) {
      for (const relationship of relationshipsResponse.items) {
        try {
          await apiRequest(page, `/api/relationships/${relationship.id}`, {
            method: "DELETE",
          });
        } catch {
          // Ignore deletion errors
        }
      }
    }

    // Get all taxonomies and delete them
    const taxonomiesResponse = await apiRequest<PaginatedResponse<Taxonomy>>(
      page,
      "/api/taxonomies",
    );
    if (taxonomiesResponse.items) {
      for (const taxonomy of taxonomiesResponse.items) {
        // Try to delete, but don't fail if it doesn't work
        try {
          await apiRequest(page, `/api/taxonomies/${taxonomy.id}`, {
            method: "DELETE",
          });
        } catch {
          // Ignore deletion errors
        }
      }
    }

    // Get all properties and delete them
    const propertiesResponse = await apiRequest<PaginatedResponse<PropertyDefinition>>(
      page,
      "/api/properties",
    );
    if (propertiesResponse.items) {
      for (const prop of propertiesResponse.items) {
        try {
          await apiRequest(page, `/api/properties/${prop.id}`, {
            method: "DELETE",
          });
        } catch {
          // Ignore deletion errors
        }
      }
    }
  } catch (_e) {
    // Ignore errors during cleanup
    console.log("Cleanup completed with some errors (expected)", _e);
  }
}
