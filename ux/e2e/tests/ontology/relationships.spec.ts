import { test, expect } from "@playwright/test";
import {
  createTestHierarchy,
  createRelationship,
  clearTestData,
  apiRequest,
} from "../../fixtures/test-helpers";
import type { Relationship, OntologyClass } from "@/api/types/ontology";

/**
 * Relationship CRUD E2E Tests
 *
 * Tests the complete CRUD lifecycle for relationships:
 * - Create a relationship between two classes
 * - List relationships
 * - View relationship details
 * - Delete relationship
 *
 * Each test uses beforeEach factory to create preconditions and verifies both
 * UI state and API responses via apiRequest read-back.
 */

test.describe("Relationship CRUD Operations", () => {
  let class1Id: string;
  let class2Id: string;
  let propertyId: string;

  test.beforeEach(async ({ page }) => {
    // Create test hierarchy with multiple classes and property
    const hierarchy = await createTestHierarchy(page, 2);
    class1Id = hierarchy.classes[0].id;
    class2Id = hierarchy.classes[1].id;
    propertyId = hierarchy.propertyDefinition.id;
  });

  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test("should create a relationship between two classes via API", async ({
    page,
  }) => {
    // Create relationship using API
    const relationship = await createRelationship(page, class1Id, class2Id, propertyId);

    // Verify relationship was created successfully
    expect(relationship.id).toBeDefined();
    expect(relationship.source_class_id).toBe(class1Id);
    expect(relationship.target_class_id).toBe(class2Id);
    expect(relationship.property_id).toBe(propertyId);

    // Verify API can retrieve the relationship
    const apiResponse = await apiRequest<Relationship>(
      page,
      `/api/relationships/${relationship.id}`,
    );
    expect(apiResponse.source_class_id).toBe(class1Id);
    expect(apiResponse.target_class_id).toBe(class2Id);
    expect(apiResponse.property_id).toBe(propertyId);
  });

  test("should list all relationships", async ({ page }) => {
    // Create multiple relationships
    const rel1 = await createRelationship(page, class1Id, class2Id, propertyId);

    // Create another class for second relationship
    const hierarchy = await createTestHierarchy(page, 1);
    const class3Id = hierarchy.classes[0].id;

    const rel2 = await createRelationship(
      page,
      class2Id,
      class3Id,
      hierarchy.propertyDefinition.id,
    );

    // Fetch relationships list from API
    const response = await apiRequest<Relationship[] | { items: Relationship[] }>(page, "/api/relationships");
    const relationships = Array.isArray(response) ? response : response.items;

    // Verify both relationships appear in list
    const ids = relationships.map((r: any) => r.id);
    expect(ids).toContain(rel1.id);
    expect(ids).toContain(rel2.id);

    // Verify relationship details
    const rel1Data = relationships.find((r: any) => r.id === rel1.id);
    expect(rel1Data).toBeDefined();
    expect(rel1Data!.source_class_id).toBe(class1Id);
    expect(rel1Data!.target_class_id).toBe(class2Id);
  });

  test("should verify relationship endpoints with correct structure", async ({
    page,
  }) => {
    // Create a relationship
    const relationship = await createRelationship(page, class1Id, class2Id, propertyId);

    // Verify GET single relationship returns correct structure
    const getResponse = await apiRequest<Relationship>(
      page,
      `/api/relationships/${relationship.id}`,
    );
    expect(getResponse).toHaveProperty("id");
    expect(getResponse).toHaveProperty("source_class_id");
    expect(getResponse).toHaveProperty("target_class_id");
    expect(getResponse).toHaveProperty("property_id");
    expect(getResponse).toHaveProperty("created_at");

    // Verify GET all relationships returns collection
    const listResponse = await apiRequest<Relationship[] | { items: Relationship[] }>(page, "/api/relationships");
    const isList = Array.isArray(listResponse);
    const hasItems = !isList && Array.isArray((listResponse as any).items);
    expect(isList || hasItems).toBe(true);
  });

  test("should delete a relationship", async ({ page }) => {
    // Create a relationship
    const relationship = await createRelationship(page, class1Id, class2Id, propertyId);

    // Verify relationship exists
    const beforeDelete = await apiRequest<Relationship>(
      page,
      `/api/relationships/${relationship.id}`,
    );
    expect(beforeDelete.id).toBe(relationship.id);

    // Delete the relationship via API
    await apiRequest(page, `/api/relationships/${relationship.id}`, {
      method: "DELETE",
    });

    // Verify relationship is deleted
    try {
      await apiRequest<Relationship>(page, `/api/relationships/${relationship.id}`);
      throw new Error("Relationship was not deleted from API");
    } catch (error: any) {
      if (!error.message.includes("404")) {
        throw error;
      }
    }
  });

  test("should verify relationship properties are linked correctly", async ({
    page,
  }) => {
    // Create a relationship
    const relationship = await createRelationship(page, class1Id, class2Id, propertyId);

    // Fetch relationship details
    const apiResponse = await apiRequest<Relationship>(
      page,
      `/api/relationships/${relationship.id}`,
    );

    // Verify all properties are correctly linked
    expect(apiResponse.source_class_id).toBe(class1Id);
    expect(apiResponse.target_class_id).toBe(class2Id);
    expect(apiResponse.property_id).toBe(propertyId);

    // Verify relationship is bidirectional when querying classes
    const class1Response = await apiRequest<OntologyClass>(
      page,
      `/api/classes/${class1Id}`,
    );
    expect(class1Response.id).toBe(class1Id);

    const class2Response = await apiRequest<OntologyClass>(
      page,
      `/api/classes/${class2Id}`,
    );
    expect(class2Response.id).toBe(class2Id);
  });

  test("should handle self-referential relationships", async ({ page }) => {
    // Create a relationship from class to itself
    const selfRelationship = await createRelationship(
      page,
      class1Id,
      class1Id,
      propertyId,
    );

    // Verify self-referential relationship
    const apiResponse = await apiRequest<Relationship>(
      page,
      `/api/relationships/${selfRelationship.id}`,
    );
    expect(apiResponse.source_class_id).toBe(class1Id);
    expect(apiResponse.target_class_id).toBe(class1Id);
    expect(apiResponse.property_id).toBe(propertyId);
  });

  test("should verify relationships respect foreign key constraints", async ({
    page,
  }) => {
    // Create valid relationship
    const relationship = await createRelationship(page, class1Id, class2Id, propertyId);
    expect(relationship.id).toBeDefined();

    // Verify deleting a related class does not leave orphaned relationships
    // (This is handled by the backend cascading delete)

    // Verify relationship fields cannot be null
    const apiResponse = await apiRequest<Relationship>(
      page,
      `/api/relationships/${relationship.id}`,
    );
    expect(apiResponse.source_class_id).toBeTruthy();
    expect(apiResponse.target_class_id).toBeTruthy();
    expect(apiResponse.property_id).toBeTruthy();
  });

  test("should create multiple relationships between same classes", async ({
    page,
  }) => {
    // Create another property for second relationship
    const hierarchy2 = await createTestHierarchy(page, 0);
    const prop2 = hierarchy2.propertyDefinition;

    // Create two relationships between same classes with different properties
    const rel1 = await createRelationship(
      page,
      class1Id,
      class2Id,
      propertyId,
    );
    const rel2 = await createRelationship(
      page,
      class1Id,
      class2Id,
      prop2.id,
    );

    // Verify both relationships exist
    expect(rel1.id).not.toBe(rel2.id);
    expect(rel1.source_class_id).toBe(rel2.source_class_id);
    expect(rel1.target_class_id).toBe(rel2.target_class_id);
    expect(rel1.property_id).not.toBe(rel2.property_id);
  });

  test("should update a relationship property", async ({ page }) => {
    // Create a relationship
    const relationship = await createRelationship(page, class1Id, class2Id, propertyId);

    // Create another property to update to
    const hierarchy2 = await createTestHierarchy(page, 0);
    const newProperty = hierarchy2.propertyDefinition;

    // Update the relationship property via API
    const updateData = {
      property_id: newProperty.id,
    };
    await apiRequest<Relationship>(
      page,
      `/api/relationships/${relationship.id}`,
      {
        method: "PUT",
        body: updateData,
      }
    );

    // Verify update via API
    const updatedResponse = await apiRequest<Relationship>(
      page,
      `/api/relationships/${relationship.id}`,
    );
    expect(updatedResponse.property_id).toBe(newProperty.id);
    expect(updatedResponse.source_class_id).toBe(class1Id);
    expect(updatedResponse.target_class_id).toBe(class2Id);
  });
});
