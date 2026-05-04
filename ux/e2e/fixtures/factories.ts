import { Page } from "@playwright/test";
import { apiRequest } from "./api-client";
import type {
  Taxonomy,
  ConceptScheme,
  OntologyClass,
  Relationship,
  PropertyDefinition,
  Individual,
} from "@/api/types/ontology";

/**
 * Test Data Factories for E2E Tests
 *
 * Provides typed factory functions and cleanup helpers for creating
 * and managing test data across ontology entities without polluting
 * the default dataset.
 *
 * All factory-created entities use a run-specific prefix/suffix
 * (timestamp + incrementing counter) to ensure uniqueness and isolation within a test run.
 */

let entityCounter = 0;

const getRunTimestamp = (): string => {
  entityCounter++;
  const timestamp = Date.now();
  return `${timestamp}-${entityCounter}`;
};

/**
 * Create a test taxonomy
 * @param page - Playwright page object
 * @param overrides - Optional fields to override defaults
 * @returns Created Taxonomy entity
 */
export async function createTaxonomy(
  page: Page,
  overrides?: { title?: string; description?: string },
): Promise<Taxonomy> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-taxonomy-${timestamp}`;
  const description =
    overrides?.description || `Test taxonomy created at ${timestamp}`;

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
 * @param page - Playwright page object
 * @param taxonomyId - ID of the parent taxonomy
 * @param overrides - Optional fields to override defaults
 * @returns Created ConceptScheme entity
 */
export async function createConceptScheme(
  page: Page,
  taxonomyId: string,
  overrides?: { title?: string; description?: string },
): Promise<ConceptScheme> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-scheme-${timestamp}`;
  const description =
    overrides?.description || `Test scheme created at ${timestamp}`;

  const response = await apiRequest<ConceptScheme>(
    page,
    `/api/taxonomies/${taxonomyId}/schemes`,
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
 * @param page - Playwright page object
 * @param schemeId - ID of the parent concept scheme
 * @param overrides - Optional fields to override defaults
 * @returns Created OntologyClass entity
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
  const description =
    overrides?.description || `Test class definition created at ${timestamp}`;

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

  const response = await apiRequest<OntologyClass>(
    page,
    `/api/schemes/${schemeId}/classes`,
    {
      method: "POST",
      body,
    },
  );

  return response;
}

/**
 * Create a test property definition
 * @param page - Playwright page object
 * @param overrides - Optional fields to override defaults
 * @returns Created PropertyDefinition entity
 */
export async function createPropertyDefinition(
  page: Page,
  overrides?: { title?: string; description?: string; identifier?: string },
): Promise<PropertyDefinition> {
  const timestamp = getRunTimestamp();
  const identifier = overrides?.identifier || `prop-${timestamp}`;
  const title = overrides?.title || `test-property-${timestamp}`;
  const description =
    overrides?.description ||
    `Test property definition created at ${timestamp}`;

  const response = await apiRequest<PropertyDefinition>(
    page,
    "/api/properties",
    {
      method: "POST",
      body: {
        identifier,
        title,
        description,
      },
    },
  );

  return response;
}

/**
 * Create a test relationship between two classes
 * @param page - Playwright page object
 * @param sourceClassId - ID of the source class
 * @param targetClassId - ID of the target class
 * @param relationshipType - Relationship type identifier (e.g., 'related_to', 'parent_of')
 * @returns Created Relationship entity
 */
export async function createRelationship(
  page: Page,
  sourceClassId: string,
  targetClassId: string,
  relationshipType: string,
): Promise<Relationship> {
  const response = await apiRequest<Relationship>(page, "/api/relationships", {
    method: "POST",
    body: {
      source_id: sourceClassId,
      target_id: targetClassId,
      relationship_type: relationshipType,
    },
  });

  return response;
}

/**
 * Create a test individual instance of one or more classes
 * @param page - Playwright page object
 * @param classIds - Array of class IDs for the individual (order matters for property precedence)
 * @param overrides - Optional fields to override defaults
 * @returns Created Individual entity
 */
export async function createIndividual(
  page: Page,
  classIds: string[],
  overrides?: {
    title?: string;
    description?: string;
  },
): Promise<Individual> {
  if (classIds.length === 0) {
    throw new Error("Individual must have at least one parent class");
  }

  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-individual-${timestamp}`;
  const description =
    overrides?.description || `Test individual created at ${timestamp}`;

  const response = await apiRequest<Individual>(page, "/api/individuals", {
    method: "POST",
    body: {
      class_ids: classIds,
      title,
      description,
    },
  });

  return response;
}

/**
 * Composite factory that creates a complete test hierarchy:
 * Taxonomy -> ConceptScheme -> OntologyClasses
 *
 * Produces a relationship-ready state with all necessary entities
 * to create relationships between classes.
 *
 * @param page - Playwright page object
 * @param classCount - Number of classes to create within the scheme (default: 1)
 * @param overrides - Optional fields to override defaults
 * @param includeIndividuals - Optional: if true, creates one Individual per class (default: false)
 * @returns Object containing created hierarchy entities and optionally individuals
 */
export async function createTestHierarchy(
  page: Page,
  classCount: number = 1,
  overrides?: {
    taxonomyTitle?: string;
    schemeTitle?: string;
    classTitle?: string;
  },
): Promise<{
  taxonomy: Taxonomy;
  scheme: ConceptScheme;
  classes: OntologyClass[];
}> {
  // Create the taxonomy
  const taxonomy = await createTaxonomy(page, {
    title: overrides?.taxonomyTitle,
  });

  // Create the concept scheme within the taxonomy
  const scheme = await createConceptScheme(page, taxonomy.id, {
    title: overrides?.schemeTitle,
  });

  // Create the requested number of classes
  const classes: OntologyClass[] = [];
  for (let i = 0; i < classCount; i++) {
    const classTitle = overrides?.classTitle
      ? `${overrides.classTitle}-${i + 1}`
      : undefined;
    const testClass = await createClass(page, scheme.id, {
      title: classTitle,
    });
    classes.push(testClass);
  }

  return {
    taxonomy,
    scheme,
    classes,
  };
}

/**
 * Seed test data with factory composition for tests that require
 * a known starting state
 *
 * Uses timestamp-based names to ensure uniqueness across repeated calls
 * within the same test run.
 *
 * @param page - Playwright page object
 * @param options - Configuration for seeded data
 * @returns Object containing all seeded entities
 */
export async function seedTestData(
  page: Page,
  options?: {
    hierarchyCount?: number;
    classesPerHierarchy?: number;
    propertiesCount?: number;
  },
): Promise<{
  hierarchies: Array<{
    taxonomy: Taxonomy;
    scheme: ConceptScheme;
    classes: OntologyClass[];
  }>;
  properties: PropertyDefinition[];
}> {
  const hierarchyCount = options?.hierarchyCount || 1;
  const classesPerHierarchy = options?.classesPerHierarchy || 2;
  const propertiesCount = options?.propertiesCount || 0;

  const hierarchies = [];
  const properties = [];

  // Create hierarchies
  for (let i = 0; i < hierarchyCount; i++) {
    const timestamp = getRunTimestamp();
    const hierarchy = await createTestHierarchy(page, classesPerHierarchy, {
      taxonomyTitle: `seed-taxonomy-${timestamp}-${i + 1}`,
      schemeTitle: `seed-scheme-${timestamp}-${i + 1}`,
      classTitle: `seed-class-${timestamp}-${i + 1}`,
    });
    hierarchies.push(hierarchy);
  }

  // Create properties if requested
  for (let i = 0; i < propertiesCount; i++) {
    const timestamp = getRunTimestamp();
    const property = await createPropertyDefinition(page, {
      title: `seed-property-${timestamp}-${i + 1}`,
    });
    properties.push(property);
  }

  return {
    hierarchies,
    properties,
  };
}

/**
 * Delete all entities in the E2E database. Safe because the database is
 * isolated (`datafiles/e2e-test/`) and wiped fresh at the start of every
 * test session by global-setup.ts.
 *
 * Deletion order respects foreign-key constraints (leaves before roots):
 * 1. Relationships
 * 2. Individuals
 * 3. Property definitions
 * 4. Ontology classes
 * 5. Concept schemes
 * 6. Taxonomies
 *
 * @param page - Playwright page object
 * @throws {Error} If any deletion step fails
 */
export async function clearTestData(page: Page): Promise<void> {
  const cleanupErrors: Array<{ step: string; error: unknown }> = [];

  const extractItems = (response: any): any[] => {
    if (Array.isArray(response)) return response;
    if (response?.items && Array.isArray(response.items)) return response.items;
    if (response?.data && Array.isArray(response.data)) return response.data;
    throw new Error(
      `Unable to extract items from API response: ${JSON.stringify(response).slice(0, 200)}`,
    );
  };

  const deleteAll = async (endpoint: string, step: string): Promise<void> => {
    try {
      const items = extractItems(await apiRequest<any>(page, endpoint));
      for (const item of items) {
        try {
          await apiRequest(page, `${endpoint}/${item.id}`, {
            method: "DELETE",
          });
        } catch (error) {
          cleanupErrors.push({ step, error });
        }
      }
    } catch (error) {
      cleanupErrors.push({ step: `${step}-fetch`, error });
    }
  };

  // Deletion order respects foreign-key constraints (leaves before roots):
  // 1. Relationships (reference classes and properties)
  // 2. Individuals (reference classes)
  // 3. Property definitions
  // 4. Classes (belong to schemes)
  // 5. Concept schemes (belong to taxonomies)
  // 6. Taxonomies
  await deleteAll("/api/relationships", "relationships");
  await deleteAll("/api/individuals", "individuals");
  await deleteAll("/api/properties", "properties");
  await deleteAll("/api/classes", "classes");
  await deleteAll("/api/schemes", "schemes");
  await deleteAll("/api/taxonomies", "taxonomies");

  if (cleanupErrors.length > 0) {
    const errorSummary = cleanupErrors
      .map(
        (e) =>
          `  - ${e.step}: ${e.error instanceof Error ? e.error.message : String(e.error)}`,
      )
      .join("\n");
    throw new Error(
      `Test data cleanup failed with ${cleanupErrors.length} error(s):\n${errorSummary}`,
    );
  }
}
