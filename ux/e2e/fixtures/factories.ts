import { Page } from "@playwright/test";
import { apiRequest } from "./api-client";
import type {
  Taxonomy,
  ConceptScheme,
  OntologyClass,
  Relationship,
  PropertyDefinition,
} from "@/api/types/ontology";

/**
 * Test Data Factories for E2E Tests
 *
 * Provides typed factory functions and cleanup helpers for creating
 * and managing test data across ontology entities without polluting
 * the default dataset.
 *
 * All factory-created entities use a run-specific prefix/suffix
 * (timestamp + random suffix) to ensure uniqueness and isolation within a test run.
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
    definition?: string;
    parent_class_id?: string;
  },
): Promise<OntologyClass> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-class-${timestamp}`;
  const definition =
    overrides?.definition || `Test class definition created at ${timestamp}`;

  const body: {
    title: string;
    definition: string;
    parent_class_id?: string;
  } = {
    title,
    definition,
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
  overrides?: { title?: string; description?: string; range?: string },
): Promise<PropertyDefinition> {
  const timestamp = getRunTimestamp();
  const title = overrides?.title || `test-property-${timestamp}`;
  const description =
    overrides?.description ||
    `Test property definition created at ${timestamp}`;
  const range = overrides?.range || "string";

  const response = await apiRequest<PropertyDefinition>(
    page,
    "/api/properties",
    {
      method: "POST",
      body: {
        title,
        description,
        range,
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
 * @param propertyId - ID of the property definition
 * @returns Created Relationship entity
 */
export async function createRelationship(
  page: Page,
  sourceClassId: string,
  targetClassId: string,
  propertyId: string,
): Promise<Relationship> {
  const response = await apiRequest<Relationship>(page, "/api/relationships", {
    method: "POST",
    body: {
      source_class_id: sourceClassId,
      target_class_id: targetClassId,
      property_id: propertyId,
    },
  });

  return response;
}

/**
 * Composite factory that creates a complete test hierarchy:
 * Taxonomy -> ConceptScheme -> OntologyClasses + PropertyDefinition
 *
 * Produces a relationship-ready state with all necessary entities
 * to create relationships between classes.
 *
 * @param page - Playwright page object
 * @param classCount - Number of classes to create within the scheme (default: 1)
 * @param overrides - Optional fields to override defaults
 * @returns Object containing created hierarchy entities including property definition
 */
export async function createTestHierarchy(
  page: Page,
  classCount: number = 1,
  overrides?: {
    taxonomyTitle?: string;
    schemeTitle?: string;
    classTitle?: string;
    propertyTitle?: string;
  },
): Promise<{
  taxonomy: Taxonomy;
  scheme: ConceptScheme;
  classes: OntologyClass[];
  propertyDefinition: PropertyDefinition;
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

  // Create a property definition for relationship support
  const propertyDefinition = await createPropertyDefinition(page, {
    title: overrides?.propertyTitle,
  });

  return {
    taxonomy,
    scheme,
    classes,
    propertyDefinition,
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
    propertyDefinition: PropertyDefinition;
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
      propertyTitle: `seed-property-${timestamp}-${i + 1}`,
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
 * Delete all factory-created test data by removing entities with
 * the run-specific timestamp prefix/suffix.
 *
 * CRITICAL: Deletion order respects foreign-key constraints:
 * 1. Relationships (must be deleted first — they reference properties and classes)
 * 2. Property definitions (must be deleted before classes, after relationships cleared)
 * 3. Ontology classes (must be deleted before schemes)
 * 4. Concept schemes (must be deleted before taxonomies)
 * 5. Taxonomies (deleted last)
 *
 * Isolation is achieved through unique names/prefixes for all test-created entities.
 * Test data is identified by name/title prefixes. Relationships are identified
 * by their source and target classes being test-created.
 *
 * @param page - Playwright page object
 * @param maxAge - Maximum age in milliseconds for entities to consider as test data (default: 10 minutes)
 * @throws {Error} If any cleanup step fails after all cleanup attempts
 */
export async function clearTestData(
  page: Page,
  maxAge: number = 10 * 60 * 1000,
): Promise<void> {
  const now = Date.now();
  const cleanupErrors: Array<{ step: string; error: unknown }> = [];

  const extractItems = (response: any): any[] => {
    if (Array.isArray(response)) {
      return response;
    }
    if (response?.items && Array.isArray(response.items)) {
      return response.items;
    }
    if (response?.data && Array.isArray(response.data)) {
      return response.data;
    }
    return [];
  };

  const isTestEntity = (entity: any, titlePatterns: string[]): boolean => {
    return titlePatterns.some((pattern) => entity.title?.includes(pattern));
  };

  const deleteEntityIfMatches = async (
    page: Page,
    entity: any,
    endpoint: string,
    titlePatterns: string[],
  ): Promise<void> => {
    if (isTestEntity(entity, titlePatterns)) {
      const createdAt = entity.created_at
        ? new Date(entity.created_at).getTime()
        : 0;
      if (now - createdAt < maxAge) {
        await apiRequest(page, `${endpoint}/${entity.id}`, {
          method: "DELETE",
        });
      }
    }
  };

  try {
    // STEP 1: Delete all test relationships (first — they reference other entities)
    // Relationships are identified by their source/target classes being test-created
    try {
      const classesResponse = await apiRequest<any>(page, "/api/classes");
      const classes = extractItems(classesResponse);
      const testClassIds = new Set(
        classes
          .filter((cls) => isTestEntity(cls, ["test-class-", "seed-class-"]))
          .map((cls) => cls.id),
      );

      const relationshipsResponse = await apiRequest<any>(
        page,
        "/api/relationships",
      );
      const relationships = extractItems(relationshipsResponse);
      for (const relationship of relationships) {
        // Only delete relationships between test-created classes
        if (
          testClassIds.has(relationship.source_class_id) &&
          testClassIds.has(relationship.target_class_id)
        ) {
          try {
            await apiRequest(page, `/api/relationships/${relationship.id}`, {
              method: "DELETE",
            });
          } catch (error) {
            cleanupErrors.push({ step: "relationships", error });
          }
        }
      }
    } catch (error) {
      cleanupErrors.push({ step: "relationships", error });
    }

    // STEP 2: Delete all test property definitions (after relationships cleared)
    try {
      const propertiesResponse = await apiRequest<any>(page, "/api/properties");
      const properties = extractItems(propertiesResponse);
      for (const property of properties) {
        try {
          await deleteEntityIfMatches(page, property, "/api/properties", [
            "test-property-",
            "seed-property-",
          ]);
        } catch (error) {
          cleanupErrors.push({ step: "properties", error });
        }
      }
    } catch (error) {
      cleanupErrors.push({ step: "properties-fetch", error });
    }

    // STEP 3: Delete all test ontology classes (after relationships cleared)
    try {
      const classesResponse = await apiRequest<any>(page, "/api/classes");
      const classes = extractItems(classesResponse);
      for (const ontologyClass of classes) {
        try {
          await deleteEntityIfMatches(page, ontologyClass, "/api/classes", [
            "test-class-",
            "seed-class-",
          ]);
        } catch (error) {
          cleanupErrors.push({ step: "classes", error });
        }
      }
    } catch (error) {
      cleanupErrors.push({ step: "classes-fetch", error });
    }

    // STEP 4: Delete all test concept schemes (after classes deleted)
    try {
      const schemesResponse = await apiRequest<any>(page, "/api/schemes");
      const schemes = extractItems(schemesResponse);
      for (const scheme of schemes) {
        try {
          await deleteEntityIfMatches(page, scheme, "/api/schemes", [
            "test-scheme-",
            "seed-scheme-",
          ]);
        } catch (error) {
          cleanupErrors.push({ step: "schemes", error });
        }
      }
    } catch (error) {
      cleanupErrors.push({ step: "schemes-fetch", error });
    }

    // STEP 5: Delete all test taxonomies (last — after all dependent entities removed)
    try {
      const taxonomiesResponse = await apiRequest<any>(page, "/api/taxonomies");
      const taxonomies = extractItems(taxonomiesResponse);
      for (const taxonomy of taxonomies) {
        try {
          await deleteEntityIfMatches(page, taxonomy, "/api/taxonomies", [
            "test-taxonomy-",
            "seed-taxonomy-",
          ]);
        } catch (error) {
          cleanupErrors.push({ step: "taxonomies", error });
        }
      }
    } catch (error) {
      cleanupErrors.push({ step: "taxonomies-fetch", error });
    }
  } catch (error) {
    cleanupErrors.push({ step: "cleanup-wrapper", error });
  }

  // Report all cleanup errors
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
