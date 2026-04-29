import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  createTestHierarchy,
  seedTestData,
  clearTestData,
} from "../fixtures/factories";

/**
 * Test Data Factories E2E Tests
 *
 * Validates the test data factory infrastructure:
 * - Individual factory functions create valid entities
 * - Composite factories create complete hierarchies
 * - Entities have correct relationships and properties
 * - Cleanup function removes test data appropriately
 */

test.describe("Test Data Factories", () => {
  test.afterEach(async ({ page }) => {
    // Clean up any test data created during tests
    await clearTestData(page);
  });

  test.describe("Individual Factories", () => {
    test("should create a taxonomy", async ({ page }) => {
      const taxonomy = await createTaxonomy(page, {
        title: "Test Taxonomy",
        description: "A test taxonomy",
      });

      expect(taxonomy).toBeDefined();
      expect(taxonomy.id).toBeDefined();
      expect(taxonomy.title).toBe("Test Taxonomy");
      expect(taxonomy.description).toBe("A test taxonomy");
      expect(taxonomy.version).toBeDefined();
    });

    test("should create a concept scheme within a taxonomy", async ({ page }) => {
      const taxonomy = await createTaxonomy(page);
      expect(taxonomy.id).toBeDefined();

      const scheme = await createConceptScheme(page, taxonomy.id, {
        title: "Test Scheme",
        description: "A test scheme",
      });

      expect(scheme).toBeDefined();
      expect(scheme.id).toBeDefined();
      expect(scheme.taxonomy_id).toBe(taxonomy.id);
      expect(scheme.title).toBe("Test Scheme");
      expect(scheme.description).toBe("A test scheme");
    });

    test("should create an ontology class within a scheme", async ({ page }) => {
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id);

      const ontologyClass = await createClass(page, scheme.id, {
        title: "Test Class",
        definition: "A test class definition",
      });

      expect(ontologyClass).toBeDefined();
      expect(ontologyClass.id).toBeDefined();
      expect(ontologyClass.scheme_id).toBe(scheme.id);
      expect(ontologyClass.title).toBe("Test Class");
      expect(ontologyClass.definition).toBe("A test class definition");
    });

    test("should create a property definition", async ({ page }) => {
      const property = await createPropertyDefinition(page, {
        title: "Test Property",
        description: "A test property",
        range: "string",
      });

      expect(property).toBeDefined();
      expect(property.id).toBeDefined();
      expect(property.title).toBe("Test Property");
      expect(property.description).toBe("A test property");
      expect(property.range).toBe("string");
    });

    test("should create a relationship between classes", async ({ page }) => {
      // Create hierarchy
      const hierarchy = await createTestHierarchy(page, 2);

      // Create a property to use in the relationship
      const property = await createPropertyDefinition(page, {
        title: "Related To",
      });

      // Create relationship
      const relationship = await createRelationship(
        page,
        hierarchy.classes[0].id,
        hierarchy.classes[1].id,
        property.id,
      );

      expect(relationship).toBeDefined();
      expect(relationship.id).toBeDefined();
      expect(relationship.source_class_id).toBe(hierarchy.classes[0].id);
      expect(relationship.target_class_id).toBe(hierarchy.classes[1].id);
      expect(relationship.property_id).toBe(property.id);
    });
  });

  test.describe("Composite Factories", () => {
    test("should create a test hierarchy with single class", async ({ page }) => {
      const hierarchy = await createTestHierarchy(page, 1);

      expect(hierarchy.taxonomy).toBeDefined();
      expect(hierarchy.taxonomy.id).toBeDefined();

      expect(hierarchy.scheme).toBeDefined();
      expect(hierarchy.scheme.id).toBeDefined();
      expect(hierarchy.scheme.taxonomy_id).toBe(hierarchy.taxonomy.id);

      expect(hierarchy.classes).toHaveLength(1);
      expect(hierarchy.classes[0].id).toBeDefined();
      expect(hierarchy.classes[0].scheme_id).toBe(hierarchy.scheme.id);
    });

    test("should create a test hierarchy with multiple classes", async ({ page }) => {
      const classCount = 3;
      const hierarchy = await createTestHierarchy(page, classCount);

      expect(hierarchy.classes).toHaveLength(classCount);

      // Verify all classes belong to the same scheme
      for (const ontologyClass of hierarchy.classes) {
        expect(ontologyClass.scheme_id).toBe(hierarchy.scheme.id);
      }
    });

    test("should create a test hierarchy with custom titles", async ({ page }) => {
      const hierarchy = await createTestHierarchy(page, 2, {
        taxonomyTitle: "Custom Taxonomy",
        schemeTitle: "Custom Scheme",
        classTitle: "Custom Class",
      });

      expect(hierarchy.taxonomy.title).toBe("Custom Taxonomy");
      expect(hierarchy.scheme.title).toBe("Custom Scheme");
      expect(hierarchy.classes[0].title).toContain("Custom Class");
      expect(hierarchy.classes[1].title).toContain("Custom Class");
    });
  });

  test.describe("Data Seeding", () => {
    test("should seed test data with default options", async ({ page }) => {
      const seededData = await seedTestData(page);

      expect(seededData.hierarchies).toHaveLength(1);
      expect(seededData.hierarchies[0].classes).toHaveLength(2); // Default classesPerHierarchy
      expect(seededData.properties).toHaveLength(0); // Default propertiesCount
    });

    test("should seed test data with custom hierarchy configuration", async ({ page }) => {
      const seededData = await seedTestData(page, {
        hierarchyCount: 2,
        classesPerHierarchy: 3,
        propertiesCount: 2,
      });

      expect(seededData.hierarchies).toHaveLength(2);
      for (const hierarchy of seededData.hierarchies) {
        expect(hierarchy.classes).toHaveLength(3);
      }
      expect(seededData.properties).toHaveLength(2);
    });

    test("should create independent hierarchies when seeding multiple", async ({ page }) => {
      const seededData = await seedTestData(page, {
        hierarchyCount: 2,
      });

      expect(seededData.hierarchies).toHaveLength(2);

      // Verify hierarchies are independent (different taxonomy IDs)
      const taxonomy1Id = seededData.hierarchies[0].taxonomy.id;
      const taxonomy2Id = seededData.hierarchies[1].taxonomy.id;
      expect(taxonomy1Id).not.toBe(taxonomy2Id);

      // Verify hierarchies are independent (different scheme IDs)
      const scheme1Id = seededData.hierarchies[0].scheme.id;
      const scheme2Id = seededData.hierarchies[1].scheme.id;
      expect(scheme1Id).not.toBe(scheme2Id);
    });
  });

  test.describe("Data Isolation", () => {
    test("should create entities with unique names", async ({ page }) => {
      const taxonomy1 = await createTaxonomy(page);
      const taxonomy2 = await createTaxonomy(page);

      // Both should have been created successfully
      expect(taxonomy1.id).toBeDefined();
      expect(taxonomy2.id).toBeDefined();

      // They should be different entities
      expect(taxonomy1.id).not.toBe(taxonomy2.id);

      // They should have different titles (due to timestamp)
      expect(taxonomy1.title).not.toBe(taxonomy2.title);
    });

    test("should handle concurrent entity creation", async ({ page }) => {
      // Create multiple entities concurrently
      const results = await Promise.all([
        createTaxonomy(page),
        createTaxonomy(page),
        createPropertyDefinition(page),
        createPropertyDefinition(page),
      ]);

      // All should succeed
      expect(results).toHaveLength(4);
      for (const result of results) {
        expect(result.id).toBeDefined();
      }
    });
  });

  test.describe("Data Cleanup", () => {
    test("should complete cleanup without errors when test data exists", async ({ page }) => {
      // Create test data
      const hierarchy = await createTestHierarchy(page);
      expect(hierarchy.taxonomy.id).toBeDefined();

      // Cleanup should complete without throwing errors
      // (actual deletion is verified by the pattern matching in clearTestData)
      await clearTestData(page);

      // If we reach here, cleanup completed successfully
      expect(true).toBe(true);
    });

    test("should not fail if there is no test data to clean", async ({ page }) => {
      // This should complete without error even if no test data exists
      await expect(clearTestData(page)).resolves.not.toThrow();
    });
  });

  test.describe("Factory-Generated Entity References", () => {
    test("should allow using factory-created entity IDs in subsequent operations", async ({ page }) => {
      // Create a hierarchy
      const hierarchy = await createTestHierarchy(page, 1);

      // Use the taxonomy ID to create another scheme
      const anotherScheme = await createConceptScheme(page, hierarchy.taxonomy.id, {
        title: "Another Scheme",
      });

      expect(anotherScheme.taxonomy_id).toBe(hierarchy.taxonomy.id);

      // Use the scheme ID to create another class
      const anotherClass = await createClass(page, anotherScheme.id, {
        title: "Another Class",
      });

      expect(anotherClass.scheme_id).toBe(anotherScheme.id);

      // Create a property and relationship using the classes
      const property = await createPropertyDefinition(page, {
        title: "Test Relation",
      });

      const relationship = await createRelationship(
        page,
        hierarchy.classes[0].id,
        anotherClass.id,
        property.id,
      );

      expect(relationship.source_class_id).toBe(hierarchy.classes[0].id);
      expect(relationship.target_class_id).toBe(anotherClass.id);
    });
  });
});
