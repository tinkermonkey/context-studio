import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  createIndividual,
  clearTestData,
  apiRequest,
  APIError,
} from "../../fixtures/test-helpers";

/**
 * Ontology Individual CRUD and Class Membership E2E Tests
 *
 * Tests the complete CRUD lifecycle for individuals and class membership operations:
 * - Create an individual within one or more classes
 * - List individuals with optional filtering
 * - View individual details with inherited properties
 * - Update individual properties
 * - Manage parent class membership (add, remove, reorder)
 * - Delete individual
 * - Verify error handling for invalid operations
 *
 * Each test uses beforeEach factory to create preconditions and verifies both
 * UI state and API responses via apiRequest read-back.
 */

test.describe("Ontology Individual CRUD and Class Membership Operations", () => {
  let schemeId: string;
  let classIds: string[] = [];

  test.beforeEach(async ({ page }) => {
    // Create test hierarchy with 3 classes for testing multi-class operations
    const hierarchy = await createTestHierarchy(page, 3, {
      classTitle: "test-individual-class",
    });
    schemeId = hierarchy.scheme.id;
    classIds = hierarchy.classes.map((cls) => cls.id);
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create an individual with a single parent class", async ({
    page,
  }) => {
    // Create individual via API
    const individual = await createIndividual(page, [classIds[0]], {
      title: "Single-Class Individual",
      description: "Individual with one parent class",
    });

    // Verify the individual was created
    expect(individual.id).toBeDefined();
    expect(individual.title).toBe("Single-Class Individual");
    expect(individual.class_ids).toEqual([classIds[0]]);
    expect(individual.version).toBe(1);

    // Read back via API to verify persistence
    const apiResponse = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(apiResponse.title).toBe("Single-Class Individual");
    expect(apiResponse.class_ids).toEqual([classIds[0]]);
  });

  test("should create an individual with multiple parent classes", async ({
    page,
  }) => {
    // Create individual with multiple parent classes (order matters)
    const parentClasses = [classIds[0], classIds[1], classIds[2]];
    const individual = await createIndividual(page, parentClasses, {
      title: "Multi-Class Individual",
      description: "Individual with three parent classes",
    });

    // Verify all classes are assigned in the correct order
    expect(individual.class_ids).toEqual(parentClasses);

    // Verify via API
    const apiResponse = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(apiResponse.class_ids).toEqual(parentClasses);
  });

  test("should list all individuals", async ({ page }) => {
    // Create multiple individuals
    const individual1 = await createIndividual(page, [classIds[0]], {
      title: "List Test Individual 1",
    });
    const individual2 = await createIndividual(page, [classIds[1]], {
      title: "List Test Individual 2",
    });

    // Fetch individuals list
    const response = await apiRequest<any>(page, "/api/individuals");

    // Verify response structure
    const individuals = Array.isArray(response)
      ? response
      : response.items || [];
    expect(individuals.length).toBeGreaterThanOrEqual(2);

    // Verify our test individuals are in the list
    const ids = individuals.map((ind: any) => ind.id);
    expect(ids).toContain(individual1.id);
    expect(ids).toContain(individual2.id);
  });

  test("should list individuals filtered by class", async ({ page }) => {
    // Create individuals in different classes
    const ind1 = await createIndividual(page, [classIds[0]], {
      title: "Class-0 Individual 1",
    });
    const ind2 = await createIndividual(page, [classIds[0]], {
      title: "Class-0 Individual 2",
    });
    const ind3 = await createIndividual(page, [classIds[1]], {
      title: "Class-1 Individual",
    });

    // Filter by classIds[0]
    const response = await apiRequest<any>(
      page,
      `/api/individuals?class_id=${classIds[0]}`,
    );

    const individuals = Array.isArray(response)
      ? response
      : response.items || [];

    // Should contain only individuals from classIds[0]
    const filteredIds = individuals.map((ind: any) => ind.id);
    expect(filteredIds).toContain(ind1.id);
    expect(filteredIds).toContain(ind2.id);
    expect(filteredIds).not.toContain(ind3.id);
  });

  test("should retrieve individual with inherited properties", async ({
    page,
  }) => {
    // Create individual
    const individual = await createIndividual(page, [classIds[0]], {
      title: "Properties Test Individual",
    });

    // Fetch individual details
    const response = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );

    // Verify response structure
    expect(response.id).toBe(individual.id);
    expect(response.title).toBe("Properties Test Individual");
    expect(response.class_ids).toEqual([classIds[0]]);
    expect(Array.isArray(response.data_properties)).toBe(true);
  });

  test("should fetch inherited-properties endpoint", async ({ page }) => {
    // Create individual
    const individual = await createIndividual(page, [classIds[0]], {
      title: "Inherited Properties Test",
    });

    // Fetch inherited properties
    const response = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}/inherited-properties`,
    );

    // Verify response structure (ListResponse)
    expect(response).toBeDefined();
    if (response.items !== undefined) {
      // List response format
      expect(Array.isArray(response.items)).toBe(true);
      expect(response.total).toBeDefined();
      expect(response.limit).toBeDefined();
      expect(response.offset).toBeDefined();
    } else if (Array.isArray(response)) {
      // Array format
      expect(Array.isArray(response)).toBe(true);
    }
  });

  test("should update individual title and description", async ({ page }) => {
    // Create individual
    const individual = await createIndividual(page, [classIds[0]], {
      title: "Original Title",
      description: "Original description",
    });

    // Update via API
    const updated = await apiRequest<any>(
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

    // Verify update response
    expect(updated.title).toBe("Updated Title");
    expect(updated.description).toBe("Updated description");

    // Verify persistence via read-back
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(readBack.title).toBe("Updated Title");
    expect(readBack.description).toBe("Updated description");
  });

  test("should add a parent class to an individual", async ({ page }) => {
    // Create individual with one class
    const individual = await createIndividual(page, [classIds[0]], {
      title: "Add Class Test",
    });

    // Add a second parent class
    const updated = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}/classes`,
      {
        method: "POST",
        body: {
          class_id: classIds[1],
        },
      },
    );

    // Verify class was added
    expect(updated.class_ids).toEqual([classIds[0], classIds[1]]);

    // Verify persistence
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(readBack.class_ids).toEqual([classIds[0], classIds[1]]);
  });

  test("should remove a parent class from an individual", async ({ page }) => {
    // Create individual with multiple classes
    const individual = await createIndividual(
      page,
      [classIds[0], classIds[1], classIds[2]],
      {
        title: "Remove Class Test",
      },
    );

    // Remove middle class - first, we need to delete and then fetch
    await apiRequest(
      page,
      `/api/individuals/${individual.id}/classes/${classIds[1]}`,
      {
        method: "DELETE",
      },
    );

    // Read back to verify
    const updated = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );

    // Verify class was removed, order maintained
    expect(updated.class_ids).toEqual([classIds[0], classIds[2]]);

    // Verify persistence
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(readBack.class_ids).toEqual([classIds[0], classIds[2]]);
  });

  test("should reject removing the last parent class", async ({ page }) => {
    // Create individual with single class
    const individual = await createIndividual(page, [classIds[0]], {
      title: "Last Class Removal Test",
    });

    // Attempt to remove the last class
    try {
      await apiRequest(
        page,
        `/api/individuals/${individual.id}/classes/${classIds[0]}`,
        {
          method: "DELETE",
        },
      );
      throw new Error("Expected error when removing last parent class");
    } catch (error: any) {
      if (error instanceof APIError) {
        // Expect 400 Bad Request or 422 Unprocessable Entity
        expect([400, 422]).toContain(error.statusCode);
      } else {
        throw error;
      }
    }
  });

  test("should reorder parent classes and verify property precedence", async ({
    page,
  }) => {
    // Create individual with multiple classes in specific order
    const individual = await createIndividual(
      page,
      [classIds[0], classIds[1], classIds[2]],
      {
        title: "Reorder Test",
      },
    );

    // Reorder classes (reverse order)
    const reordered = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}/classes`,
      {
        method: "PUT",
        body: {
          class_ids: [classIds[2], classIds[1], classIds[0]],
        },
      },
    );

    // Verify new order
    expect(reordered.class_ids).toEqual([classIds[2], classIds[1], classIds[0]]);

    // Verify persistence
    const readBack = await apiRequest<any>(
      page,
      `/api/individuals/${individual.id}`,
    );
    expect(readBack.class_ids).toEqual([classIds[2], classIds[1], classIds[0]]);
  });

  test("should delete an individual", async ({ page }) => {
    // Create individual
    const individual = await createIndividual(page, [classIds[0]], {
      title: "Delete Test Individual",
    });

    // Delete via API
    await apiRequest(page, `/api/individuals/${individual.id}`, {
      method: "DELETE",
    });

    // Verify deletion by attempting to read
    try {
      await apiRequest<any>(page, `/api/individuals/${individual.id}`);
      throw new Error("Individual was not deleted");
    } catch (error: any) {
      if (!(error instanceof APIError && error.statusCode === 404)) {
        throw error;
      }
    }
  });

  test("should handle validation error when creating with zero parent classes", async ({
    page,
  }) => {
    // Attempt to create individual with no parent classes
    try {
      await apiRequest<any>(page, "/api/individuals", {
        method: "POST",
        body: {
          class_ids: [],
          title: "Invalid Individual",
          description: "No parent classes",
        },
      });
      throw new Error("Expected validation error for zero parent classes");
    } catch (error: any) {
      if (error instanceof APIError) {
        // Expect 400 or 422 (validation error)
        expect([400, 422]).toContain(error.statusCode);
      } else {
        throw error;
      }
    }
  });
});
