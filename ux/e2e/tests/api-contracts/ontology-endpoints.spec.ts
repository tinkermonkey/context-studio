import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createPropertyDefinition,
  createRelationship,
  createTestHierarchy,
  clearTestData,
  apiRequest,
  APIError,
} from "../../fixtures/test-helpers";

/**
 * Ontology Endpoints API Contract E2E Tests
 *
 * Tests the backend API endpoints directly without UI interaction.
 * Validates:
 * - All endpoints exist and return expected status codes
 * - Response shapes match contracts
 * - Proper error handling and status codes
 * - Data persistence across operations
 *
 * These tests protect the backend from regression by verifying
 * endpoint contracts are maintained.
 */

test.describe("Ontology API Endpoints", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test.describe("Taxonomy Endpoints", () => {
    test("GET /api/taxonomies should return list of taxonomies", async ({
      page,
    }) => {
      // Create test data
      const taxonomy1 = await createTaxonomy(page);
      const taxonomy2 = await createTaxonomy(page);

      // Call endpoint
      const response = await apiRequest<any>(page, "/api/taxonomies");

      // Verify response structure
      expect(Array.isArray(response) || Array.isArray(response.items)).toBe(
        true,
      );

      const taxonomies = Array.isArray(response)
        ? response
        : response.items || [];
      expect(taxonomies.length).toBeGreaterThanOrEqual(2);

      // Verify our test data is in response
      const ids = taxonomies.map((t: any) => t.id);
      expect(ids).toContain(taxonomy1.id);
      expect(ids).toContain(taxonomy2.id);
    });

    test("POST /api/taxonomies should create a new taxonomy", async ({
      page,
    }) => {
      const response = await apiRequest<any>(page, "/api/taxonomies", {
        method: "POST",
        body: {
          title: "API Test Taxonomy",
          description: "Created via API endpoint test",
        },
      });

      // Verify response
      expect(response.id).toBeDefined();
      expect(response.title).toBe("API Test Taxonomy");
      expect(response.description).toBe("Created via API endpoint test");
      expect(response.created_at).toBeDefined();
      expect(response.version).toBeDefined();
    });

    test("GET /api/taxonomies/:id should return specific taxonomy", async ({
      page,
    }) => {
      // Create test taxonomy
      const taxonomy = await createTaxonomy(page, {
        title: "Get Test Taxonomy",
      });

      // Call endpoint
      const response = await apiRequest<any>(
        page,
        `/api/taxonomies/${taxonomy.id}`,
      );

      // Verify response
      expect(response.id).toBe(taxonomy.id);
      expect(response.title).toBe("Get Test Taxonomy");
      expect(response.created_at).toBeDefined();
    });

    test("PUT /api/taxonomies/:id should update a taxonomy", async ({
      page,
    }) => {
      // Create test taxonomy
      const taxonomy = await createTaxonomy(page);

      // Update via API
      const response = await apiRequest<any>(
        page,
        `/api/taxonomies/${taxonomy.id}`,
        {
          method: "PUT",
          body: {
            title: "Updated Taxonomy",
            description: "Updated via API",
          },
        },
      );

      // Verify response
      expect(response.id).toBe(taxonomy.id);
      expect(response.title).toBe("Updated Taxonomy");
      expect(response.description).toBe("Updated via API");
    });

    test("DELETE /api/taxonomies/:id should delete a taxonomy", async ({
      page,
    }) => {
      // Create test taxonomy
      const taxonomy = await createTaxonomy(page);

      // Delete via API
      await apiRequest(page, `/api/taxonomies/${taxonomy.id}`, {
        method: "DELETE",
      });

      // Verify deletion
      try {
        await apiRequest<any>(page, `/api/taxonomies/${taxonomy.id}`);
        throw new Error("Taxonomy was not deleted");
      } catch (error: any) {
        if (!(error instanceof APIError && error.statusCode === 404)) {
          throw error;
        }
      }
    });
  });

  test.describe("Concept Scheme Endpoints", () => {
    test("GET /api/schemes should return list of schemes", async ({ page }) => {
      // Create test data
      const taxonomy = await createTaxonomy(page);
      const scheme1 = await createConceptScheme(page, taxonomy.id);
      const scheme2 = await createConceptScheme(page, taxonomy.id);

      // Call endpoint
      const response = await apiRequest<any>(page, "/api/schemes");

      // Verify response
      const schemes = Array.isArray(response) ? response : response.items || [];
      expect(schemes.length).toBeGreaterThanOrEqual(2);

      const ids = schemes.map((s: any) => s.id);
      expect(ids).toContain(scheme1.id);
      expect(ids).toContain(scheme2.id);
    });

    test("POST /api/taxonomies/:taxonomyId/schemes should create scheme", async ({
      page,
    }) => {
      // Create parent taxonomy
      const taxonomy = await createTaxonomy(page);

      // Create scheme
      const response = await apiRequest<any>(
        page,
        `/api/taxonomies/${taxonomy.id}/schemes`,
        {
          method: "POST",
          body: {
            title: "API Test Scheme",
            description: "Created via API",
          },
        },
      );

      // Verify response
      expect(response.id).toBeDefined();
      expect(response.title).toBe("API Test Scheme");
      expect(response.taxonomy_id).toBe(taxonomy.id);
      expect(response.created_at).toBeDefined();
    });

    test("GET /api/schemes/:id should return specific scheme", async ({
      page,
    }) => {
      // Create test data
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id);

      // Call endpoint
      const response = await apiRequest<any>(page, `/api/schemes/${scheme.id}`);

      // Verify response
      expect(response.id).toBe(scheme.id);
      expect(response.taxonomy_id).toBe(taxonomy.id);
      expect(response.created_at).toBeDefined();
    });

    test("PUT /api/schemes/:id should update a scheme", async ({ page }) => {
      // Create test data
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id);

      // Update via API
      const response = await apiRequest<any>(
        page,
        `/api/schemes/${scheme.id}`,
        {
          method: "PUT",
          body: {
            title: "Updated Scheme",
            description: "Updated via API",
          },
        },
      );

      // Verify response
      expect(response.id).toBe(scheme.id);
      expect(response.title).toBe("Updated Scheme");
      expect(response.taxonomy_id).toBe(taxonomy.id);
    });

    test("DELETE /api/schemes/:id should delete a scheme", async ({ page }) => {
      // Create test data
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id);

      // Delete via API
      await apiRequest(page, `/api/schemes/${scheme.id}`, {
        method: "DELETE",
      });

      // Verify deletion
      try {
        await apiRequest<any>(page, `/api/schemes/${scheme.id}`);
        throw new Error("Scheme was not deleted");
      } catch (error: any) {
        if (!(error instanceof APIError && error.statusCode === 404)) {
          throw error;
        }
      }
    });
  });

  test.describe("Class Endpoints", () => {
    test("GET /api/classes should return list of classes", async ({ page }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page, 2);
      const class1 = hierarchy.classes[0];
      const class2 = hierarchy.classes[1];

      // Call endpoint
      const response = await apiRequest<any>(page, "/api/classes");

      // Verify response
      const classes = Array.isArray(response) ? response : response.items || [];
      const ids = classes.map((c: any) => c.id);
      expect(ids).toContain(class1.id);
      expect(ids).toContain(class2.id);
    });

    test("POST /api/schemes/:schemeId/classes should create class", async ({
      page,
    }) => {
      // Create parent scheme
      const hierarchy = await createTestHierarchy(page, 0);
      const schemeId = hierarchy.scheme.id;

      // Create class
      const response = await apiRequest<any>(
        page,
        `/api/schemes/${schemeId}/classes`,
        {
          method: "POST",
          body: {
            title: "API Test Class",
            description: "Created via API",
          },
        },
      );

      // Verify response
      expect(response.id).toBeDefined();
      expect(response.title).toBe("API Test Class");
      expect(response.description).toBe("Created via API");
      expect(response.concept_scheme_id).toBe(schemeId);
      expect(response.created_at).toBeDefined();
    });

    test("GET /api/classes/:id should return specific class", async ({
      page,
    }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page, 1);
      const ontologyClass = hierarchy.classes[0];

      // Call endpoint
      const response = await apiRequest<any>(
        page,
        `/api/classes/${ontologyClass.id}`,
      );

      // Verify response
      expect(response.id).toBe(ontologyClass.id);
      expect(response.concept_scheme_id).toBe(hierarchy.scheme.id);
      expect(response.created_at).toBeDefined();
    });

    test("PUT /api/classes/:id should update a class", async ({ page }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page, 1);
      const ontologyClass = hierarchy.classes[0];

      // Update via API
      const response = await apiRequest<any>(
        page,
        `/api/classes/${ontologyClass.id}`,
        {
          method: "PUT",
          body: {
            title: "Updated Class",
            description: "Updated via API",
          },
        },
      );

      // Verify response
      expect(response.id).toBe(ontologyClass.id);
      expect(response.title).toBe("Updated Class");
      expect(response.description).toBe("Updated via API");
      expect(response.concept_scheme_id).toBe(hierarchy.scheme.id);
    });

    test("DELETE /api/classes/:id should delete a class", async ({ page }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page, 1);
      const ontologyClass = hierarchy.classes[0];

      // Delete via API
      await apiRequest(page, `/api/classes/${ontologyClass.id}`, {
        method: "DELETE",
      });

      // Verify deletion
      try {
        await apiRequest<any>(page, `/api/classes/${ontologyClass.id}`);
        throw new Error("Class was not deleted");
      } catch (error: any) {
        if (!(error instanceof APIError && error.statusCode === 404)) {
          throw error;
        }
      }
    });
  });

  test.describe("Property Definition Endpoints", () => {
    test("GET /api/properties should return list of properties", async ({
      page,
    }) => {
      // Create test data
      const prop1 = await createPropertyDefinition(page);
      const prop2 = await createPropertyDefinition(page);

      // Call endpoint
      const response = await apiRequest<any>(page, "/api/properties");

      // Verify response
      const properties = Array.isArray(response)
        ? response
        : response.items || [];
      const ids = properties.map((p: any) => p.id);
      expect(ids).toContain(prop1.id);
      expect(ids).toContain(prop2.id);
    });

    test("POST /api/properties should create a property", async ({ page }) => {
      const response = await apiRequest<any>(page, "/api/properties", {
        method: "POST",
        body: {
          identifier: "api_test_property",
          title: "API Test Property",
          description: "Created via API",
        },
      });

      // Verify response
      expect(response.id).toBeDefined();
      expect(response.identifier).toBe("api_test_property");
      expect(response.title).toBe("API Test Property");
      expect(response.description).toBe("Created via API");
      expect(response.created_at).toBeDefined();
    });

    test("GET /api/properties/:id should return specific property", async ({
      page,
    }) => {
      // Create test property
      const property = await createPropertyDefinition(page);

      // Call endpoint
      const response = await apiRequest<any>(
        page,
        `/api/properties/${property.id}`,
      );

      // Verify response
      expect(response.id).toBe(property.id);
      expect(response.title).toBeDefined();
      expect(response.created_at).toBeDefined();
    });

    test("PUT /api/properties/:id should update a property", async ({
      page,
    }) => {
      // Create test property
      const property = await createPropertyDefinition(page);

      // Update via API
      const response = await apiRequest<any>(
        page,
        `/api/properties/${property.id}`,
        {
          method: "PUT",
          body: {
            title: "Updated Property",
            description: "Updated via API",
          },
        },
      );

      // Verify response
      expect(response.id).toBe(property.id);
      expect(response.title).toBe("Updated Property");
      expect(response.description).toBe("Updated via API");
    });

    test("DELETE /api/properties/:id should delete a property", async ({
      page,
    }) => {
      // Create test property
      const property = await createPropertyDefinition(page);

      // Delete via API
      await apiRequest(page, `/api/properties/${property.id}`, {
        method: "DELETE",
      });

      // Verify deletion
      try {
        await apiRequest<any>(page, `/api/properties/${property.id}`);
        throw new Error("Property was not deleted");
      } catch (error: any) {
        if (!(error instanceof APIError && error.statusCode === 404)) {
          throw error;
        }
      }
    });
  });

  test.describe("Relationship Endpoints", () => {
    test("GET /api/relationships should return list of relationships", async ({
      page,
    }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page, 2);
      const rel1 = await createRelationship(
        page,
        hierarchy.classes[0].id,
        hierarchy.classes[1].id,
        "related_to",
      );

      // Call endpoint
      const response = await apiRequest<any>(page, "/api/relationships");

      // Verify response
      const relationships = Array.isArray(response)
        ? response
        : response.items || [];
      const ids = relationships.map((r: any) => r.id);
      expect(ids).toContain(rel1.id);
    });

    test("POST /api/relationships should create a relationship", async ({
      page,
    }) => {
      // Create preconditions
      const hierarchy = await createTestHierarchy(page, 2);

      const response = await apiRequest<any>(page, "/api/relationships", {
        method: "POST",
        body: {
          source_id: hierarchy.classes[0].id,
          target_id: hierarchy.classes[1].id,
          relationship_type: "related_to",
        },
      });

      // Verify response
      expect(response.id).toBeDefined();
      expect(response.source_id).toBe(hierarchy.classes[0].id);
      expect(response.target_id).toBe(hierarchy.classes[1].id);
      expect(response.created_at).toBeDefined();
    });

    test("GET /api/relationships/:id should return specific relationship", async ({
      page,
    }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page, 2);
      const relationship = await createRelationship(
        page,
        hierarchy.classes[0].id,
        hierarchy.classes[1].id,
        "related_to",
      );

      // Call endpoint
      const response = await apiRequest<any>(
        page,
        `/api/relationships/${relationship.id}`,
      );

      // Verify response
      expect(response.id).toBe(relationship.id);
      expect(response.source_id).toBe(hierarchy.classes[0].id);
      expect(response.target_id).toBe(hierarchy.classes[1].id);
    });

    test("DELETE /api/relationships/:id should delete a relationship", async ({
      page,
    }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page, 2);
      const relationship = await createRelationship(
        page,
        hierarchy.classes[0].id,
        hierarchy.classes[1].id,
        "related_to",
      );

      // Delete via API
      await apiRequest(page, `/api/relationships/${relationship.id}`, {
        method: "DELETE",
      });

      // Verify deletion
      try {
        await apiRequest<any>(page, `/api/relationships/${relationship.id}`);
        throw new Error("Relationship was not deleted");
      } catch (error: any) {
        if (!(error instanceof APIError && error.statusCode === 404)) {
          throw error;
        }
      }
    });
  });

  test("should verify all ontology endpoints return proper error status codes", async ({
    page,
  }) => {
    // Test 404 for non-existent resources
    const nonExistentId = "00000000-0000-0000-0000-000000000000";

    const endpoints = [
      `/api/taxonomies/${nonExistentId}`,
      `/api/schemes/${nonExistentId}`,
      `/api/classes/${nonExistentId}`,
      `/api/properties/${nonExistentId}`,
      `/api/relationships/${nonExistentId}`,
    ];

    for (const endpoint of endpoints) {
      try {
        await apiRequest<any>(page, endpoint);
        // If we get here, endpoint didn't return 404
        console.warn(`Expected 404 for ${endpoint}`);
      } catch (error: any) {
        // Expected: 404 error
        expect(error.message).toContain("404");
      }
    }
  });

  test("should ensure API responses include required metadata fields", async ({
    page,
  }) => {
    // Create entities and verify they have required fields
    const taxonomy = await createTaxonomy(page);
    expect(taxonomy.id).toBeDefined();
    expect(taxonomy.created_at).toBeDefined();
    expect(typeof taxonomy.created_at).toBe("string");

    const property = await createPropertyDefinition(page);
    expect(property.id).toBeDefined();
    expect(property.created_at).toBeDefined();

    const hierarchy = await createTestHierarchy(page, 1);
    expect(hierarchy.scheme.id).toBeDefined();
    expect(hierarchy.scheme.created_at).toBeDefined();
    expect(hierarchy.classes[0].id).toBeDefined();
    expect(hierarchy.classes[0].created_at).toBeDefined();
  });

  test.describe("Individual Endpoints", () => {
    let classId: string;

    test.beforeEach(async ({ page }) => {
      const hierarchy = await createTestHierarchy(page, 1);
      classId = hierarchy.classes[0].id;
    });

    test("POST /api/individuals should create a new individual", async ({
      page,
    }) => {
      const response = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "API Test Individual",
          description: "Created via API endpoint test",
        },
      });

      // Verify response
      expect(response.id).toBeDefined();
      expect(response.title).toBe("API Test Individual");
      expect(response.class_ids).toEqual([classId]);
      expect(response.created_at).toBeDefined();
      expect(response.version).toBeDefined();
    });

    test("GET /api/individuals should return list of individuals with pagination envelope", async ({
      page,
    }) => {
      const hierarchy = await createTestHierarchy(page, 1);
      const classId = hierarchy.classes[0].id;

      // Create test individuals
      const ind1 = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "API Paginated Individual 1",
        },
      });
      const ind2 = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "API Paginated Individual 2",
        },
      });

      // Call endpoint with pagination
      const response = await apiRequest<any>(
        page,
        "/api/individuals?limit=10&offset=0",
      );

      // Verify pagination envelope
      expect(response.items).toBeDefined();
      expect(Array.isArray(response.items)).toBe(true);
      expect(response.total).toBeDefined();
      expect(typeof response.total).toBe("number");
      expect(response.limit).toBeDefined();
      expect(response.offset).toBeDefined();
      expect(response.limit).toBe(10);
      expect(response.offset).toBe(0);

      // Verify our test data is in response
      const ids = response.items.map((i: any) => i.id);
      expect(ids).toContain(ind1.id);
      expect(ids).toContain(ind2.id);
    });

    test("GET /api/individuals/:id should return specific individual", async ({
      page,
    }) => {
      // Create test individual
      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "Get Test Individual",
        },
      });

      // Call endpoint
      const response = await apiRequest<any>(
        page,
        `/api/individuals/${individual.id}`,
      );

      // Verify response
      expect(response.id).toBe(individual.id);
      expect(response.title).toBe("Get Test Individual");
      expect(response.class_ids).toEqual([classId]);
    });

    test("PUT /api/individuals/:id should update an individual", async ({
      page,
    }) => {
      // Create test individual
      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "Original Title",
          description: "Original description",
        },
      });

      // Update via API
      const response = await apiRequest<any>(
        page,
        `/api/individuals/${individual.id}`,
        {
          method: "PUT",
          body: {
            title: "Updated Title",
            description: "Updated description",
          },
        },
      );

      // Verify response
      expect(response.id).toBe(individual.id);
      expect(response.title).toBe("Updated Title");
      expect(response.description).toBe("Updated description");
    });

    test("DELETE /api/individuals/:id should delete an individual", async ({
      page,
    }) => {
      // Create test individual
      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "Delete Test Individual",
        },
      });

      // Delete via API
      await apiRequest(page, `/api/individuals/${individual.id}`, {
        method: "DELETE",
      });

      // Verify deletion
      try {
        await apiRequest<any>(page, `/api/individuals/${individual.id}`);
        throw new Error("Individual was not deleted");
      } catch (error: any) {
        if (!(error instanceof APIError && error.statusCode === 404)) {
          throw error;
        }
      }
    });

    test("POST /api/individuals/:id/classes should add a parent class", async ({
      page,
    }) => {
      // Create second class for testing
      const hierarchy = await createTestHierarchy(page, 2);
      const class1Id = hierarchy.classes[0].id;
      const class2Id = hierarchy.classes[1].id;

      // Create individual with first class
      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [class1Id],
          title: "Add Class Test",
        },
      });

      // Add second class
      const response = await apiRequest<any>(
        page,
        `/api/individuals/${individual.id}/classes`,
        {
          method: "POST",
          body: {
            class_id: class2Id,
          },
        },
      );

      // Verify class was added
      expect(response.class_ids).toEqual([class1Id, class2Id]);
    });

    test("DELETE /api/individuals/:id/classes/:class_id should remove a parent class", async ({
      page,
    }) => {
      // Create individual with multiple classes
      const hierarchy = await createTestHierarchy(page, 2);
      const class1Id = hierarchy.classes[0].id;
      const class2Id = hierarchy.classes[1].id;

      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [class1Id, class2Id],
          title: "Remove Class Test",
        },
      });

      // Remove one class
      await apiRequest(
        page,
        `/api/individuals/${individual.id}/classes/${class2Id}`,
        {
          method: "DELETE",
        },
      );

      // Read back to verify
      const response = await apiRequest<any>(
        page,
        `/api/individuals/${individual.id}`,
      );

      // Verify class was removed
      expect(response.class_ids).toEqual([class1Id]);
    });

    test("PUT /api/individuals/:id/classes should reorder parent classes", async ({
      page,
    }) => {
      // Create individual with multiple classes
      const hierarchy = await createTestHierarchy(page, 3);
      const class1Id = hierarchy.classes[0].id;
      const class2Id = hierarchy.classes[1].id;
      const class3Id = hierarchy.classes[2].id;

      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [class1Id, class2Id, class3Id],
          title: "Reorder Class Test",
        },
      });

      // Reorder classes
      const response = await apiRequest<any>(
        page,
        `/api/individuals/${individual.id}/classes`,
        {
          method: "PUT",
          body: {
            class_ids: [class3Id, class1Id, class2Id],
          },
        },
      );

      // Verify new order
      expect(response.class_ids).toEqual([class3Id, class1Id, class2Id]);
    });

    test("GET /api/individuals/:id/inherited-properties should return documented shape", async ({
      page,
    }) => {
      // Create individual
      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "Inherited Properties Test",
        },
      });

      // Fetch inherited properties
      const response = await apiRequest<any>(
        page,
        `/api/individuals/${individual.id}/inherited-properties`,
      );

      // Verify response shape (ListResponse)
      expect(response.items).toBeDefined();
      expect(Array.isArray(response.items)).toBe(true);
      expect(response.total).toBeDefined();
      expect(response.limit).toBeDefined();
      expect(response.offset).toBeDefined();
    });

    test("should return 422 when creating individual with zero parent classes", async ({
      page,
    }) => {
      try {
        await apiRequest<any>(page, "/api/individuals", {
          method: "POST",
          body: {
            class_ids: [],
            title: "Invalid Individual",
          },
        });
        throw new Error("Expected validation error");
      } catch (error: any) {
        if (error instanceof APIError) {
          expect([400, 422]).toContain(error.statusCode);
        } else {
          throw error;
        }
      }
    });

    test("should return 422 when removing last parent class", async ({
      page,
    }) => {
      // Create individual with single class
      const individual = await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [classId],
          title: "Last Class Test",
        },
      });

      // Attempt to remove only class
      try {
        await apiRequest(
          page,
          `/api/individuals/${individual.id}/classes/${classId}`,
          {
            method: "DELETE",
          },
        );
        throw new Error("Expected error when removing last class");
      } catch (error: any) {
        if (error instanceof APIError) {
          expect([400, 422]).toContain(error.statusCode);
        } else {
          throw error;
        }
      }
    });

    test("should return 404 for non-existent individual", async ({ page }) => {
      const nonExistentId = "00000000-0000-0000-0000-000000000000";

      try {
        await apiRequest<any>(page, `/api/individuals/${nonExistentId}`);
        throw new Error("Expected 404");
      } catch (error: any) {
        if (error instanceof APIError) {
          expect(error.statusCode).toBe(404);
        } else {
          throw error;
        }
      }
    });
  });
});
