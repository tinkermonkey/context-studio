/**
 * Unit tests for OntologyService using MSW to mock HTTP responses.
 * Tests verify:
 * - Correct HTTP method and URL construction
 * - Response parsing and return value
 * - ApiError thrown on 4xx/5xx with status and detail
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ontologyService } from "../ontology";
import {
  createTaxonomy,
  createListTaxonomies,
  createTaxonomyCreateRequest,
  createConceptScheme,
  createListSchemes,
  createConceptSchemeCreateRequest,
  createClass,
  createListClasses,
  createClassCreateRequest,
  createIndividual,
  createListIndividuals,
  createIndividualCreateRequest,
  createPropertyDefinition,
  createListProperties,
  createPropertyDefinitionCreateRequest,
  createRelationship,
  createListRelationships,
  createRelationshipCreateRequest,
  createPublishDiffStats,
  createDataPropertyValue,
  createListDataPropertyValues,
} from "./fixtures/ontology.fixtures";

// Initialize MSW server for all tests
const server = setupServer();

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

// ============================================================================
// Taxonomy Tests
// ============================================================================

describe("OntologyService - Taxonomies", () => {
  describe("listTaxonomies", () => {
    it("returns list of taxonomies from GET /api/taxonomies", async () => {
      const mockTaxonomies = createListTaxonomies([
        createTaxonomy({ id: "tax-1", title: "Biology" }),
        createTaxonomy({ id: "tax-2", title: "Chemistry" }),
      ]);

      server.use(http.get("*/api/taxonomies", () => HttpResponse.json(mockTaxonomies)));

      const result = await ontologyService.listTaxonomies();

      expect(result).toEqual(mockTaxonomies);
      expect(result.items).toHaveLength(2);
      expect(result.items[0].title).toBe("Biology");
    });

    it("throws ApiError on 500 from listTaxonomies", async () => {
      server.use(
        http.get("*/api/taxonomies", () =>
          HttpResponse.json(
            {
              detail: "Internal server error",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(ontologyService.listTaxonomies()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
        detail: expect.stringContaining("Internal server error"),
      });
    });
  });

  describe("getTaxonomy", () => {
    it("returns taxonomy by ID from GET /api/taxonomies/:id", async () => {
      const mockTaxonomy = createTaxonomy({
        id: "tax-123",
        title: "Biology",
      });

      server.use(http.get("*/api/taxonomies/tax-123", () => HttpResponse.json(mockTaxonomy)));

      const result = await ontologyService.getTaxonomy("tax-123");

      expect(result).toEqual(mockTaxonomy);
      expect(result.id).toBe("tax-123");
      expect(result.title).toBe("Biology");
    });

    it("throws ApiError with 404 on getTaxonomy with non-existent ID", async () => {
      server.use(
        http.get("*/api/taxonomies/not-found", () =>
          HttpResponse.json(
            {
              detail: "Taxonomy not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.getTaxonomy("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
        detail: expect.stringContaining("Taxonomy not found"),
      });
    });
  });

  describe("createTaxonomy", () => {
    it("creates and returns taxonomy from POST /api/taxonomies", async () => {
      const createRequest = createTaxonomyCreateRequest({
        title: "New Biology",
      });
      const mockResponse = createTaxonomy({
        id: "tax-999",
        title: "New Biology",
      });

      server.use(http.post("*/api/taxonomies", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.createTaxonomy(createRequest);

      expect(result).toEqual(mockResponse);
      expect(result.id).toBe("tax-999");
      expect(result.title).toBe("New Biology");
    });

    it("throws ApiError with 400 on createTaxonomy with invalid data", async () => {
      const createRequest = createTaxonomyCreateRequest({ title: "" });

      server.use(
        http.post("*/api/taxonomies", () =>
          HttpResponse.json(
            {
              detail: "Title cannot be empty",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(ontologyService.createTaxonomy(createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
        detail: expect.stringContaining("Title cannot be empty"),
      });
    });

    it("throws ApiError with 409 on createTaxonomy with duplicate title", async () => {
      const createRequest = createTaxonomyCreateRequest({
        title: "Existing",
      });

      server.use(
        http.post("*/api/taxonomies", () =>
          HttpResponse.json(
            {
              detail: "Taxonomy with this title already exists",
            },
            { status: 409 },
          ),
        ),
      );

      await expect(ontologyService.createTaxonomy(createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 409,
        detail: expect.stringContaining("already exists"),
      });
    });
  });

  describe("updateTaxonomy", () => {
    it("updates and returns taxonomy from PUT /api/taxonomies/:id", async () => {
      const updateRequest = { title: "Updated Biology" };
      const mockResponse = createTaxonomy({
        id: "tax-123",
        title: "Updated Biology",
      });

      server.use(http.put("*/api/taxonomies/tax-123", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.updateTaxonomy("tax-123", updateRequest);

      expect(result).toEqual(mockResponse);
      expect(result.title).toBe("Updated Biology");
    });

    it("throws ApiError with 404 on updateTaxonomy with non-existent ID", async () => {
      const updateRequest = { title: "Updated" };

      server.use(
        http.put("*/api/taxonomies/not-found", () =>
          HttpResponse.json(
            {
              detail: "Taxonomy not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.updateTaxonomy("not-found", updateRequest),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deleteTaxonomy", () => {
    it("deletes taxonomy via DELETE /api/taxonomies/:id", async () => {
      server.use(
        http.delete("*/api/taxonomies/tax-123", () => new HttpResponse(null, { status: 204 })),
      );

      await expect(ontologyService.deleteTaxonomy("tax-123")).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteTaxonomy with non-existent ID", async () => {
      server.use(
        http.delete("*/api/taxonomies/not-found", () =>
          HttpResponse.json(
            {
              detail: "Taxonomy not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.deleteTaxonomy("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });

    it("throws ApiError with 422 on deleteTaxonomy with child schemes", async () => {
      server.use(
        http.delete("*/api/taxonomies/tax-123", () =>
          HttpResponse.json(
            {
              detail: "Cannot delete taxonomy with concept schemes",
            },
            { status: 422 },
          ),
        ),
      );

      await expect(ontologyService.deleteTaxonomy("tax-123")).rejects.toMatchObject({
        name: "ApiError",
        status: 422,
        detail: expect.stringContaining("concept schemes"),
      });
    });
  });

  describe("getPublishDiffStats", () => {
    it("returns publish diff stats from GET /api/taxonomies/:id/publish-diff", async () => {
      const mockStats = createPublishDiffStats({
        added: 5,
        modified: 3,
        removed: 1,
      });

      server.use(
        http.get("*/api/taxonomies/tax-123/publish-diff", () => HttpResponse.json(mockStats)),
      );

      const result = await ontologyService.getPublishDiffStats("tax-123");

      expect(result).toEqual(mockStats);
      expect(result.added).toBe(5);
      expect(result.modified).toBe(3);
      expect(result.removed).toBe(1);
    });

    it("throws ApiError with 404 on getPublishDiffStats with non-existent taxonomy", async () => {
      server.use(
        http.get("*/api/taxonomies/not-found/publish-diff", () =>
          HttpResponse.json(
            {
              detail: "Taxonomy not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.getPublishDiffStats("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("publishTaxonomy", () => {
    it("publishes taxonomy from POST /api/taxonomies/:id/publish", async () => {
      const mockTaxonomy = createTaxonomy({
        id: "tax-123",
        status: "published",
      });

      server.use(
        http.post("*/api/taxonomies/tax-123/publish", () => HttpResponse.json(mockTaxonomy)),
      );

      const result = await ontologyService.publishTaxonomy("tax-123", "Release version 1.0");

      expect(result).toEqual(mockTaxonomy);
      expect(result.status).toBe("published");
    });

    it("throws ApiError with 400 on publishTaxonomy with invalid commit message", async () => {
      server.use(
        http.post("*/api/taxonomies/tax-123/publish", () =>
          HttpResponse.json(
            {
              detail: "Commit message is required",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(ontologyService.publishTaxonomy("tax-123", "")).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });
});

// ============================================================================
// Concept Scheme Tests
// ============================================================================

describe("OntologyService - Concept Schemes", () => {
  describe("listSchemes", () => {
    it("returns all schemes from GET /api/schemes", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({ id: "scheme-1", title: "Animals" }),
        createConceptScheme({ id: "scheme-2", title: "Plants" }),
      ]);

      server.use(http.get("*/api/schemes", () => HttpResponse.json(mockSchemes)));

      const result = await ontologyService.listSchemes();

      expect(result).toEqual(mockSchemes);
      expect(result.items).toHaveLength(2);
    });

    it("filters schemes by taxonomy_id via query params", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({ id: "scheme-1", taxonomy_id: "tax-123" }),
      ]);

      server.use(
        http.get("*/api/schemes", ({ request }) => {
          const url = new URL(request.url);
          if (url.searchParams.get("taxonomy_id") === "tax-123") {
            return HttpResponse.json(mockSchemes);
          }
          return HttpResponse.json(createListSchemes([]));
        }),
      );

      const result = await ontologyService.listSchemes("tax-123");

      expect(result.items).toHaveLength(1);
      expect(result.items[0].taxonomy_id).toBe("tax-123");
    });

    it("throws ApiError on 500 from listSchemes", async () => {
      server.use(
        http.get("*/api/schemes", () =>
          HttpResponse.json(
            {
              detail: "Internal server error",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(ontologyService.listSchemes()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getScheme", () => {
    it("returns scheme by ID from GET /api/schemes/:id", async () => {
      const mockScheme = createConceptScheme({
        id: "scheme-123",
        title: "Animals",
      });

      server.use(http.get("*/api/schemes/scheme-123", () => HttpResponse.json(mockScheme)));

      const result = await ontologyService.getScheme("scheme-123");

      expect(result).toEqual(mockScheme);
    });

    it("throws ApiError with 404 on getScheme with non-existent ID", async () => {
      server.use(
        http.get("*/api/schemes/not-found", () =>
          HttpResponse.json(
            {
              detail: "Concept scheme not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.getScheme("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createScheme", () => {
    it("creates scheme under taxonomy from POST /api/taxonomies/:taxonomyId/schemes", async () => {
      const createRequest = createConceptSchemeCreateRequest({
        title: "New Scheme",
      });
      const mockResponse = createConceptScheme({
        id: "scheme-999",
        title: "New Scheme",
        taxonomy_id: "tax-123",
      });

      server.use(
        http.post("*/api/taxonomies/tax-123/schemes", () => HttpResponse.json(mockResponse)),
      );

      const result = await ontologyService.createScheme("tax-123", createRequest);

      expect(result).toEqual(mockResponse);
      expect(result.taxonomy_id).toBe("tax-123");
    });

    it("throws ApiError with 404 on createScheme with non-existent taxonomy", async () => {
      const createRequest = createConceptSchemeCreateRequest();

      server.use(
        http.post("*/api/taxonomies/not-found/schemes", () =>
          HttpResponse.json(
            {
              detail: "Taxonomy not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.createScheme("not-found", createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("updateScheme", () => {
    it("updates scheme from PUT /api/schemes/:id", async () => {
      const updateRequest = { title: "Updated Scheme" };
      const mockResponse = createConceptScheme({
        id: "scheme-123",
        title: "Updated Scheme",
      });

      server.use(http.put("*/api/schemes/scheme-123", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.updateScheme("scheme-123", updateRequest);

      expect(result.title).toBe("Updated Scheme");
    });

    it("throws ApiError with 404 on updateScheme with non-existent ID", async () => {
      server.use(
        http.put("*/api/schemes/not-found", () =>
          HttpResponse.json(
            {
              detail: "Scheme not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.updateScheme("not-found", { title: "Updated" }),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deleteScheme", () => {
    it("deletes scheme via DELETE /api/schemes/:id", async () => {
      server.use(
        http.delete("*/api/schemes/scheme-123", () => new HttpResponse(null, { status: 204 })),
      );

      await expect(ontologyService.deleteScheme("scheme-123")).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteScheme with non-existent ID", async () => {
      server.use(
        http.delete("*/api/schemes/not-found", () =>
          HttpResponse.json(
            {
              detail: "Scheme not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.deleteScheme("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});

// ============================================================================
// Class Tests
// ============================================================================

describe("OntologyService - Classes", () => {
  describe("listClasses", () => {
    it("returns all classes from GET /api/classes", async () => {
      const mockClasses = createListClasses([
        createClass({ id: "class-1", title: "Dog" }),
        createClass({ id: "class-2", title: "Cat" }),
      ]);

      server.use(http.get("*/api/classes", () => HttpResponse.json(mockClasses)));

      const result = await ontologyService.listClasses();

      expect(result.items).toHaveLength(2);
    });

    it("filters classes by concept_scheme_id and parent_class_id", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          concept_scheme_id: "scheme-123",
          parent_class_id: "class-parent",
        }),
      ]);

      server.use(
        http.get("*/api/classes", ({ request }) => {
          const url = new URL(request.url);
          const hasScheme = url.searchParams.get("concept_scheme_id") === "scheme-123";
          const hasParent = url.searchParams.get("parent_class_id") === "class-parent";

          if (hasScheme && hasParent) {
            return HttpResponse.json(mockClasses);
          }
          return HttpResponse.json(createListClasses([]));
        }),
      );

      const result = await ontologyService.listClasses({
        concept_scheme_id: "scheme-123",
        parent_class_id: "class-parent",
      });

      expect(result.items).toHaveLength(1);
    });

    it("throws ApiError on 500 from listClasses", async () => {
      server.use(
        http.get("*/api/classes", () =>
          HttpResponse.json(
            {
              detail: "Internal server error",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(ontologyService.listClasses()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getClass", () => {
    it("returns class by ID from GET /api/classes/:id", async () => {
      const mockClass = createClass({
        id: "class-123",
        title: "Dog",
      });

      server.use(http.get("*/api/classes/class-123", () => HttpResponse.json(mockClass)));

      const result = await ontologyService.getClass("class-123");

      expect(result).toEqual(mockClass);
    });

    it("throws ApiError with 404 on getClass with non-existent ID", async () => {
      server.use(
        http.get("*/api/classes/not-found", () =>
          HttpResponse.json(
            {
              detail: "Class not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.getClass("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createClass", () => {
    it("creates class under scheme from POST /api/schemes/:schemeId/classes", async () => {
      const createRequest = createClassCreateRequest({ title: "Dog" });
      const mockResponse = createClass({
        id: "class-999",
        title: "Dog",
        concept_scheme_id: "scheme-123",
      });

      server.use(
        http.post("*/api/schemes/scheme-123/classes", () => HttpResponse.json(mockResponse)),
      );

      const result = await ontologyService.createClass("scheme-123", createRequest);

      expect(result.concept_scheme_id).toBe("scheme-123");
    });

    it("throws ApiError with 404 on createClass with non-existent scheme", async () => {
      const createRequest = createClassCreateRequest();

      server.use(
        http.post("*/api/schemes/not-found/classes", () =>
          HttpResponse.json(
            {
              detail: "Scheme not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.createClass("not-found", createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("updateClass", () => {
    it("updates class from PUT /api/classes/:id", async () => {
      const updateRequest = { title: "Updated Dog" };
      const mockResponse = createClass({
        id: "class-123",
        title: "Updated Dog",
      });

      server.use(http.put("*/api/classes/class-123", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.updateClass("class-123", updateRequest);

      expect(result.title).toBe("Updated Dog");
    });

    it("throws ApiError with 404 on updateClass with non-existent ID", async () => {
      server.use(
        http.put("*/api/classes/not-found", () =>
          HttpResponse.json(
            {
              detail: "Class not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.updateClass("not-found", { title: "Updated" }),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("moveClass", () => {
    it("moves class to new concept scheme from POST /api/classes/:id/move", async () => {
      const moveRequest = { target_scheme_id: "scheme-new" };
      const mockResponse = createClass({
        id: "class-123",
        concept_scheme_id: "scheme-new",
      });

      server.use(http.post("*/api/classes/class-123/move", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.moveClass("class-123", moveRequest);

      expect(result.concept_scheme_id).toBe("scheme-new");
    });

    it("throws ApiError with 400 on moveClass with invalid scheme", async () => {
      const moveRequest = { target_scheme_id: "invalid" };

      server.use(
        http.post("*/api/classes/class-123/move", () =>
          HttpResponse.json(
            {
              detail: "Target scheme not found",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(ontologyService.moveClass("class-123", moveRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("deleteClass", () => {
    it("deletes class via DELETE /api/classes/:id", async () => {
      server.use(
        http.delete("*/api/classes/class-123", () => new HttpResponse(null, { status: 204 })),
      );

      await expect(ontologyService.deleteClass("class-123")).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteClass with non-existent ID", async () => {
      server.use(
        http.delete("*/api/classes/not-found", () =>
          HttpResponse.json(
            {
              detail: "Class not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.deleteClass("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});

// ============================================================================
// Individual Tests
// ============================================================================

describe("OntologyService - Individuals", () => {
  describe("listIndividuals", () => {
    it("returns all individuals from GET /api/individuals", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({ id: "ind-1", title: "Fido" }),
        createIndividual({ id: "ind-2", title: "Fluffy" }),
      ]);

      server.use(http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)));

      const result = await ontologyService.listIndividuals();

      expect(result.items).toHaveLength(2);
    });

    it("filters individuals by class_id", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-1",
          class_ids: ["class-dog"],
        }),
      ]);

      server.use(
        http.get("*/api/individuals", ({ request }) => {
          const url = new URL(request.url);
          if (url.searchParams.get("class_id") === "class-dog") {
            return HttpResponse.json(mockIndividuals);
          }
          return HttpResponse.json(createListIndividuals([]));
        }),
      );

      const result = await ontologyService.listIndividuals({
        class_id: "class-dog",
      });

      expect(result.items).toHaveLength(1);
    });

    it("throws ApiError on 500 from listIndividuals", async () => {
      server.use(
        http.get("*/api/individuals", () =>
          HttpResponse.json(
            {
              detail: "Internal server error",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(ontologyService.listIndividuals()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getIndividual", () => {
    it("returns individual by ID from GET /api/individuals/:id", async () => {
      const mockIndividual = createIndividual({
        id: "ind-123",
        title: "Fido",
      });

      server.use(http.get("*/api/individuals/ind-123", () => HttpResponse.json(mockIndividual)));

      const result = await ontologyService.getIndividual("ind-123");

      expect(result).toEqual(mockIndividual);
    });

    it("throws ApiError with 404 on getIndividual with non-existent ID", async () => {
      server.use(
        http.get("*/api/individuals/not-found", () =>
          HttpResponse.json(
            {
              detail: "Individual not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.getIndividual("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createIndividual", () => {
    it("creates individual from POST /api/individuals", async () => {
      const createRequest = createIndividualCreateRequest({
        title: "Fido",
        class_ids: ["class-dog"],
      });
      const mockResponse = createIndividual({
        id: "ind-999",
        title: "Fido",
        class_ids: ["class-dog"],
      });

      server.use(http.post("*/api/individuals", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.createIndividual(createRequest);

      expect(result.id).toBe("ind-999");
      expect(result.class_ids).toContain("class-dog");
    });

    it("throws ApiError with 400 on createIndividual with invalid class", async () => {
      const createRequest = createIndividualCreateRequest({
        class_ids: ["invalid-class"],
      });

      server.use(
        http.post("*/api/individuals", () =>
          HttpResponse.json(
            {
              detail: "One or more classes not found",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(ontologyService.createIndividual(createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("updateIndividual", () => {
    it("updates individual from PUT /api/individuals/:id", async () => {
      const updateRequest = { title: "Updated Fido" };
      const mockResponse = createIndividual({
        id: "ind-123",
        title: "Updated Fido",
      });

      server.use(http.put("*/api/individuals/ind-123", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.updateIndividual("ind-123", updateRequest);

      expect(result.title).toBe("Updated Fido");
    });

    it("throws ApiError with 404 on updateIndividual with non-existent ID", async () => {
      server.use(
        http.put("*/api/individuals/not-found", () =>
          HttpResponse.json(
            {
              detail: "Individual not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.updateIndividual("not-found", { title: "Updated" }),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deleteIndividual", () => {
    it("deletes individual via DELETE /api/individuals/:id", async () => {
      server.use(
        http.delete("*/api/individuals/ind-123", () => new HttpResponse(null, { status: 204 })),
      );

      await expect(ontologyService.deleteIndividual("ind-123")).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteIndividual with non-existent ID", async () => {
      server.use(
        http.delete("*/api/individuals/not-found", () =>
          HttpResponse.json(
            {
              detail: "Individual not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.deleteIndividual("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("addParentClass", () => {
    it("adds parent class to individual from POST /api/individuals/:individualId/classes", async () => {
      const classRequest = { class_id: "class-new" };
      const mockResponse = createIndividual({
        id: "ind-123",
        class_ids: ["class-old", "class-new"],
      });

      server.use(
        http.post("*/api/individuals/ind-123/classes", () => HttpResponse.json(mockResponse)),
      );

      const result = await ontologyService.addParentClass("ind-123", classRequest);

      expect(result.class_ids).toContain("class-new");
    });

    it("throws ApiError with 404 on addParentClass with non-existent individual", async () => {
      const classRequest = { class_id: "class-new" };

      server.use(
        http.post("*/api/individuals/not-found/classes", () =>
          HttpResponse.json(
            {
              detail: "Individual not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.addParentClass("not-found", classRequest)).rejects.toMatchObject(
        {
          name: "ApiError",
          status: 404,
        },
      );
    });
  });

  describe("removeParentClass", () => {
    it("removes parent class from individual via DELETE /api/individuals/:individualId/classes/:classId", async () => {
      server.use(
        http.delete(
          "*/api/individuals/ind-123/classes/class-old",
          () => new HttpResponse(null, { status: 204 }),
        ),
      );

      await expect(
        ontologyService.removeParentClass("ind-123", "class-old"),
      ).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on removeParentClass with non-existent individual", async () => {
      server.use(
        http.delete("*/api/individuals/not-found/classes/class-old", () =>
          HttpResponse.json(
            {
              detail: "Individual not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.removeParentClass("not-found", "class-old"),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("reorderIndividualClasses", () => {
    it("reorders classes on individual from PUT /api/individuals/:individualId/classes", async () => {
      const reorderRequest = {
        class_ids: ["class-2", "class-1", "class-3"],
      };
      const mockResponse = createIndividual({
        id: "ind-123",
        class_ids: ["class-2", "class-1", "class-3"],
      });

      server.use(
        http.put("*/api/individuals/ind-123/classes", () => HttpResponse.json(mockResponse)),
      );

      const result = await ontologyService.reorderIndividualClasses("ind-123", reorderRequest);

      expect(result.class_ids).toEqual(["class-2", "class-1", "class-3"]);
    });

    it("throws ApiError with 404 on reorderIndividualClasses with non-existent individual", async () => {
      const reorderRequest = {
        class_ids: ["class-1"],
      };

      server.use(
        http.put("*/api/individuals/not-found/classes", () =>
          HttpResponse.json(
            {
              detail: "Individual not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.reorderIndividualClasses("not-found", reorderRequest),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("getIndividualInheritedProperties", () => {
    it("returns inherited properties for individual from GET /api/individuals/:id/inherited-properties", async () => {
      const mockProperties = createListDataPropertyValues([
        createDataPropertyValue({ property_identifier: "color", value: "Brown" }),
        createDataPropertyValue({ property_identifier: "size", value: "Large" }),
      ]);

      server.use(
        http.get("*/api/individuals/ind-123/inherited-properties", () =>
          HttpResponse.json(mockProperties),
        ),
      );

      const result = await ontologyService.getIndividualInheritedProperties("ind-123");

      expect(result.items).toHaveLength(2);
      expect(result.items[0].property_identifier).toBe("color");
    });

    it("throws ApiError with 404 on getIndividualInheritedProperties with non-existent individual", async () => {
      server.use(
        http.get("*/api/individuals/not-found/inherited-properties", () =>
          HttpResponse.json(
            {
              detail: "Individual not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.getIndividualInheritedProperties("not-found"),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});

// ============================================================================
// Property Definition Tests
// ============================================================================

describe("OntologyService - Property Definitions", () => {
  describe("listProperties", () => {
    it("returns all properties from GET /api/properties", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "Color" }),
        createPropertyDefinition({ id: "prop-2", title: "Size" }),
      ]);

      server.use(http.get("*/api/properties", () => HttpResponse.json(mockProperties)));

      const result = await ontologyService.listProperties();

      expect(result.items).toHaveLength(2);
    });

    it("filters properties by is_relevant", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "Important" }),
      ]);

      server.use(
        http.get("*/api/properties", ({ request }) => {
          const url = new URL(request.url);
          if (url.searchParams.get("is_relevant") === "true") {
            return HttpResponse.json(mockProperties);
          }
          return HttpResponse.json(createListProperties([]));
        }),
      );

      const result = await ontologyService.listProperties(true);

      expect(result.items).toHaveLength(1);
    });

    it("throws ApiError on 500 from listProperties", async () => {
      server.use(
        http.get("*/api/properties", () =>
          HttpResponse.json(
            {
              detail: "Internal server error",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(ontologyService.listProperties()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getProperty", () => {
    it("returns property by ID from GET /api/properties/:id", async () => {
      const mockProperty = createPropertyDefinition({
        id: "prop-123",
        title: "Color",
      });

      server.use(http.get("*/api/properties/prop-123", () => HttpResponse.json(mockProperty)));

      const result = await ontologyService.getProperty("prop-123");

      expect(result).toEqual(mockProperty);
    });

    it("throws ApiError with 404 on getProperty with non-existent ID", async () => {
      server.use(
        http.get("*/api/properties/not-found", () =>
          HttpResponse.json(
            {
              detail: "Property not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.getProperty("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createProperty", () => {
    it("creates property from POST /api/properties", async () => {
      const createRequest = createPropertyDefinitionCreateRequest({
        title: "Color",
      });
      const mockResponse = createPropertyDefinition({
        id: "prop-999",
        title: "Color",
      });

      server.use(http.post("*/api/properties", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.createProperty(createRequest);

      expect(result.id).toBe("prop-999");
      expect(result.title).toBe("Color");
    });

    it("throws ApiError with 400 on createProperty with invalid data", async () => {
      const createRequest = createPropertyDefinitionCreateRequest({
        title: "",
      });

      server.use(
        http.post("*/api/properties", () =>
          HttpResponse.json(
            {
              detail: "Title cannot be empty",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(ontologyService.createProperty(createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("updateProperty", () => {
    it("updates property from PUT /api/properties/:id", async () => {
      const updateRequest = { title: "Updated Color" };
      const mockResponse = createPropertyDefinition({
        id: "prop-123",
        title: "Updated Color",
      });

      server.use(http.put("*/api/properties/prop-123", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.updateProperty("prop-123", updateRequest);

      expect(result.title).toBe("Updated Color");
    });

    it("throws ApiError with 404 on updateProperty with non-existent ID", async () => {
      server.use(
        http.put("*/api/properties/not-found", () =>
          HttpResponse.json(
            {
              detail: "Property not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(
        ontologyService.updateProperty("not-found", { title: "Updated" }),
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deleteProperty", () => {
    it("deletes property via DELETE /api/properties/:id", async () => {
      server.use(
        http.delete("*/api/properties/prop-123", () => new HttpResponse(null, { status: 204 })),
      );

      await expect(ontologyService.deleteProperty("prop-123")).resolves.toBeDefined();
    });

    it("throws ApiError with 422 on deleteProperty with dependent relationships", async () => {
      server.use(
        http.delete("*/api/properties/prop-123", () =>
          HttpResponse.json(
            {
              detail: "Cannot delete property with existing relationships",
            },
            { status: 422 },
          ),
        ),
      );

      await expect(ontologyService.deleteProperty("prop-123")).rejects.toMatchObject({
        name: "ApiError",
        status: 422,
        detail: expect.stringContaining("relationships"),
      });
    });
  });
});

// ============================================================================
// Relationship Tests
// ============================================================================

describe("OntologyService - Relationships", () => {
  describe("listRelationships", () => {
    it("returns all relationships from GET /api/relationships", async () => {
      const mockRelationships = createListRelationships([
        createRelationship({ id: "rel-1" }),
        createRelationship({ id: "rel-2" }),
      ]);

      server.use(http.get("*/api/relationships", () => HttpResponse.json(mockRelationships)));

      const result = await ontologyService.listRelationships();

      expect(result.items).toHaveLength(2);
    });

    it("filters relationships by source_id, target_id, and property_id", async () => {
      const mockRelationships = createListRelationships([
        createRelationship({
          id: "rel-1",
          source_id: "class-1",
          target_id: "class-2",
          property_definition_id: "prop-123",
        }),
      ]);

      server.use(
        http.get("*/api/relationships", ({ request }) => {
          const url = new URL(request.url);
          const hasSource = url.searchParams.get("source_id") === "class-1";
          const hasTarget = url.searchParams.get("target_id") === "class-2";
          const hasProperty = url.searchParams.get("property_id") === "prop-123";

          if (hasSource && hasTarget && hasProperty) {
            return HttpResponse.json(mockRelationships);
          }
          return HttpResponse.json(createListRelationships([]));
        }),
      );

      const result = await ontologyService.listRelationships({
        source_id: "class-1",
        target_id: "class-2",
        property_id: "prop-123",
      });

      expect(result.items).toHaveLength(1);
    });

    it("throws ApiError on 500 from listRelationships", async () => {
      server.use(
        http.get("*/api/relationships", () =>
          HttpResponse.json(
            {
              detail: "Internal server error",
            },
            { status: 500 },
          ),
        ),
      );

      await expect(ontologyService.listRelationships()).rejects.toMatchObject({
        name: "ApiError",
        status: 500,
      });
    });
  });

  describe("getRelationship", () => {
    it("returns relationship by ID from GET /api/relationships/:id", async () => {
      const mockRelationship = createRelationship({
        id: "rel-123",
      });

      server.use(
        http.get("*/api/relationships/rel-123", () => HttpResponse.json(mockRelationship)),
      );

      const result = await ontologyService.getRelationship("rel-123");

      expect(result).toEqual(mockRelationship);
    });

    it("throws ApiError with 404 on getRelationship with non-existent ID", async () => {
      server.use(
        http.get("*/api/relationships/not-found", () =>
          HttpResponse.json(
            {
              detail: "Relationship not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.getRelationship("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("createRelationship", () => {
    it("creates relationship from POST /api/relationships", async () => {
      const createRequest = createRelationshipCreateRequest();
      const mockResponse = createRelationship({
        id: "rel-999",
      });

      server.use(http.post("*/api/relationships", () => HttpResponse.json(mockResponse)));

      const result = await ontologyService.createRelationship(createRequest);

      expect(result.id).toBe("rel-999");
    });

    it("throws ApiError with 400 on createRelationship with invalid classes", async () => {
      const createRequest = createRelationshipCreateRequest({
        source_id: "invalid",
      });

      server.use(
        http.post("*/api/relationships", () =>
          HttpResponse.json(
            {
              detail: "Source class not found",
            },
            { status: 400 },
          ),
        ),
      );

      await expect(ontologyService.createRelationship(createRequest)).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("deleteRelationship", () => {
    it("deletes relationship via DELETE /api/relationships/:id", async () => {
      server.use(
        http.delete("*/api/relationships/rel-123", () => new HttpResponse(null, { status: 204 })),
      );

      await expect(ontologyService.deleteRelationship("rel-123")).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteRelationship with non-existent ID", async () => {
      server.use(
        http.delete("*/api/relationships/not-found", () =>
          HttpResponse.json(
            {
              detail: "Relationship not found",
            },
            { status: 404 },
          ),
        ),
      );

      await expect(ontologyService.deleteRelationship("not-found")).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});
