import { test, expect } from "@playwright/test";
import {
  createTaxonomy,
  createConceptScheme,
  createClass,
  createPropertyDefinition,
  createRelationship,
  createTestHierarchy,
  clearTestData,
} from "../../fixtures/test-helpers";

/**
 * Test Data Factory API Contract Tests
 *
 * Validates that factory helpers correctly call the backend APIs and that
 * responses match the expected shapes. These are pure API tests — no UI
 * interactions — so they belong in api-contracts/.
 */

test.describe("Test Data Factories", () => {
  test.afterEach(async ({ page }) => {
    await clearTestData(page);
  });

  test.describe("Individual Factories", () => {
    test("should create a taxonomy", async ({ page }) => {
      const taxonomy = await createTaxonomy(page, {
        title: "test-taxonomy-basic",
        description: "A test taxonomy",
      });

      expect(taxonomy.id).toBeDefined();
      expect(taxonomy.title).toBe("test-taxonomy-basic");
      expect(taxonomy.description).toBe("A test taxonomy");
    });

    test("should create a concept scheme within a taxonomy", async ({
      page,
    }) => {
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id, {
        title: "Test Scheme",
        description: "A test scheme",
      });

      expect(scheme.id).toBeDefined();
      expect(scheme.taxonomy_id).toBe(taxonomy.id);
      expect(scheme.title).toBe("Test Scheme");
      expect(scheme.description).toBe("A test scheme");
    });

    test("should create an ontology class within a scheme", async ({
      page,
    }) => {
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id);
      const ontologyClass = await createClass(page, scheme.id, {
        title: "Test Class",
        description: "A test class definition",
      });

      expect(ontologyClass.id).toBeDefined();
      expect(ontologyClass.concept_scheme_id).toBe(scheme.id);
      expect(ontologyClass.title).toBe("Test Class");
      expect(ontologyClass.description).toBe("A test class definition");
    });

    test("should create a property definition", async ({ page }) => {
      const property = await createPropertyDefinition(page, {
        title: "Test Property",
        identifier: "test_property",
        description: "A test property",
      });

      expect(property.id).toBeDefined();
      expect(property.title).toBe("Test Property");
      expect(property.identifier).toBe("test_property");
    });

    test("should create a relationship between classes", async ({ page }) => {
      const taxonomy = await createTaxonomy(page);
      const scheme = await createConceptScheme(page, taxonomy.id);
      const class1 = await createClass(page, scheme.id);
      const class2 = await createClass(page, scheme.id);
      const relationship = await createRelationship(
        page,
        class1.id,
        class2.id,
        "related_to",
      );

      expect(relationship.id).toBeDefined();
      expect(relationship.source_id).toBe(class1.id);
      expect(relationship.target_id).toBe(class2.id);
    });
  });

  test.describe("Composite Factories", () => {
    test("should create a test hierarchy with taxonomy, scheme, and classes", async ({
      page,
    }) => {
      const hierarchy = await createTestHierarchy(page, 3);

      expect(hierarchy.taxonomy.id).toBeDefined();
      expect(hierarchy.scheme.id).toBeDefined();
      expect(hierarchy.classes).toHaveLength(3);
      expect(hierarchy.scheme.taxonomy_id).toBe(hierarchy.taxonomy.id);
      for (const cls of hierarchy.classes) {
        expect(cls.concept_scheme_id).toBe(hierarchy.scheme.id);
      }
    });

    test("should create hierarchy with custom class title prefix", async ({
      page,
    }) => {
      const hierarchy = await createTestHierarchy(page, 2, {
        classTitle: "custom-class",
      });

      expect(hierarchy.classes).toHaveLength(2);
      for (const cls of hierarchy.classes) {
        expect(cls.title).toContain("custom-class");
      }
    });
  });
});
