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

// Type definitions for pipelines
export interface Pipeline {
  id: string;
  title: string;
  provider: string;
  model: string;
  system_prompt: string;
  user_prompt: string;
  config?: Record<string, unknown>;
  version: number;
  enabled: boolean;
  created_at: string;
  last_updated: string;
}

export interface Execution {
  id: string;
  pipeline_config_id: string;
  output_text: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  duration_ms: number;
  status: "success" | "error" | "timeout";
  error_message?: string | null;
  timestamp: string;
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
 * Create a test pipeline configuration
 */
export async function createPipeline(
  page: Page,
  overrides?: {
    title?: string;
    provider?: string;
    model?: string;
    system_prompt?: string;
    user_prompt?: string;
    config?: Record<string, unknown>;
    pipeline?: string;
  },
): Promise<Pipeline> {
  const timestamp = getRunTimestamp();
  const pipeline = overrides?.pipeline || `test-pipeline-slug-${timestamp}`;
  const title = overrides?.title || `test-pipeline-${timestamp}`;
  const provider = overrides?.provider || "openai";
  const model = overrides?.model || "gpt-4";
  const system_prompt = overrides?.system_prompt || "You are a helpful assistant.";
  const user_prompt = overrides?.user_prompt || "Process the following: {input}";
  const config = overrides?.config || {};

  const response = await apiRequest<Pipeline>(page, "/api/pipelines", {
    method: "POST",
    body: {
      pipeline,
      title,
      provider,
      model,
      system_prompt,
      user_prompt,
      config,
    },
  });

  return response;
}

/**
 * Execute a pipeline and get the execution result
 */
export async function executePipeline(
  page: Page,
  pipelineId: string,
): Promise<Execution> {
  const response = await apiRequest<Execution>(page, `/api/pipelines/${pipelineId}/execute`, {
    method: "POST",
    body: {
      input_text: "Test input for pipeline execution",
    },
  });

  return response;
}

/**
 * Get pipeline executions
 */
export async function getPipelineExecutions(
  page: Page,
  pipelineId: string,
): Promise<Execution[]> {
  const response = await apiRequest<Execution[]>(page, `/api/pipelines/${pipelineId}/executions`);
  return response;
}

interface PaginatedResponse<T> {
  items: T[];
}

/**
 * Clear all test data by deleting all non-default entities
 * Handles cascading deletes and soft-deleted entities
 */
export async function clearTestData(page: Page): Promise<void> {
  try {
    // Delete individuals first (they have fewer dependencies)
    const individualsResponse = await apiRequest<PaginatedResponse<Individual>>(
      page,
      "/api/individuals",
    );
    if (individualsResponse.items) {
      for (const individual of individualsResponse.items) {
        try {
          await apiRequest(page, `/api/individuals/${individual.id}`, {
            method: "DELETE",
          });
        } catch {
          // Ignore - already deleted or other error
        }
      }
    }

    // Delete all relationships (depends on classes and properties)
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
          // Ignore - may already be deleted
        }
      }
    }

    // Delete all pipelines
    try {
      const pipelinesResponse = await apiRequest<Pipeline[]>(page, "/api/pipelines");
      if (Array.isArray(pipelinesResponse)) {
        for (const pipeline of pipelinesResponse) {
          try {
            await apiRequest(page, `/api/pipelines/${pipeline.id}`, { method: "DELETE" });
          } catch {
            // Ignore deletion errors
          }
        }
      }
    } catch {
      // Ignore if pipelines endpoint doesn't exist
    }

    // Delete all properties (can be used by relationships)
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

    // Delete all taxonomies (will cascade to schemes and classes)
    const taxonomiesResponse = await apiRequest<PaginatedResponse<Taxonomy>>(
      page,
      "/api/taxonomies",
    );
    if (taxonomiesResponse.items) {
      for (const taxonomy of taxonomiesResponse.items) {
        try {
          await apiRequest(page, `/api/taxonomies/${taxonomy.id}`, {
            method: "DELETE",
          });
        } catch {
          // Ignore - may be in use or already deleted
        }
      }
    }

    // Add a small delay to ensure database operations complete
    await page.waitForLoadState("networkidle");
  } catch {
    // Ignore errors during cleanup - tests may not have created data
    // but we still want cleanup to succeed
  }
}

/**
 * Get individuals by class ID (for checking cascade deletion)
 */
export async function getIndividualsByClass(
  page: Page,
  classId: string,
): Promise<Individual[]> {
  const response = await apiRequest<PaginatedResponse<Individual>>(page, "/api/individuals", {
    method: "GET",
  });
  if (response.items) {
    return response.items.filter((ind) => ind.class_ids.includes(classId));
  }
  return [];
}
