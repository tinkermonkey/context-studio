/**
 * Unit tests for OntologyService using MSW to mock HTTP responses.
 * Tests verify:
 * - Correct HTTP method and URL construction
 * - Response parsing and return value
 * - ApiError thrown on 4xx/5xx with status and detail
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { rest } from "msw";
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

      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) => res(ctx.json(mockTaxonomies)))
      );

      const result = await ontologyService.listTaxonomies();

      expect(result).toEqual(mockTaxonomies);
      expect(result.items).toHaveLength(2);
      expect(result.items[0].title).toBe("Biology");
    });

    it("throws ApiError on 500 from listTaxonomies", async () => {
      server.use(
        rest.get("*/api/taxonomies", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
          detail: "Internal server error",
        })
      )
        )
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

      server.use(
        rest.get("*/api/taxonomies/tax-123", (req, res, ctx) => res(ctx.json(mockTaxonomy)))
      );

      const result = await ontologyService.getTaxonomy("tax-123");

      expect(result).toEqual(mockTaxonomy);
      expect(result.id).toBe("tax-123");
      expect(result.title).toBe("Biology");
    });

    it("throws ApiError with 404 on getTaxonomy with non-existent ID", async () => {
      server.use(
        rest.get("*/api/taxonomies/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Taxonomy not found",
        })
      )
        )
      );

      await expect(
        ontologyService.getTaxonomy("not-found")
      ).rejects.toMatchObject({
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

      server.use(
        rest.post("*/api/taxonomies", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.createTaxonomy(createRequest);

      expect(result).toEqual(mockResponse);
      expect(result.id).toBe("tax-999");
      expect(result.title).toBe("New Biology");
    });

    it("throws ApiError with 400 on createTaxonomy with invalid data", async () => {
      const createRequest = createTaxonomyCreateRequest({ title: "" });

      server.use(
        rest.post("*/api/taxonomies", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
          detail: "Title cannot be empty",
        })
      )
        )
      );

      await expect(
        ontologyService.createTaxonomy(createRequest)
      ).rejects.toMatchObject({
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
        rest.post("*/api/taxonomies", (req, res, ctx) =>
          res(
        ctx.status(409),
        ctx.json({
          detail: "Taxonomy with this title already exists",
        })
      )
        )
      );

      await expect(
        ontologyService.createTaxonomy(createRequest)
      ).rejects.toMatchObject({
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

      server.use(
        rest.put("*/api/taxonomies/tax-123", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.updateTaxonomy("tax-123", updateRequest);

      expect(result).toEqual(mockResponse);
      expect(result.title).toBe("Updated Biology");
    });

    it("throws ApiError with 404 on updateTaxonomy with non-existent ID", async () => {
      const updateRequest = { title: "Updated" };

      server.use(
        rest.put("*/api/taxonomies/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Taxonomy not found",
        })
      )
        )
      );

      await expect(
        ontologyService.updateTaxonomy("not-found", updateRequest)
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("deleteTaxonomy", () => {
    it("deletes taxonomy via DELETE /api/taxonomies/:id", async () => {
      server.use(
        rest.delete("*/api/taxonomies/tax-123", (req, res, ctx) => res(ctx.status(204)))
      );

      await expect(
        ontologyService.deleteTaxonomy("tax-123")
      ).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteTaxonomy with non-existent ID", async () => {
      server.use(
        rest.delete("*/api/taxonomies/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Taxonomy not found",
        })
      )
        )
      );

      await expect(
        ontologyService.deleteTaxonomy("not-found")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });

    it("throws ApiError with 422 on deleteTaxonomy with child schemes", async () => {
      server.use(
        rest.delete("*/api/taxonomies/tax-123", (req, res, ctx) =>
          res(
        ctx.status(422),
        ctx.json({
          detail: "Cannot delete taxonomy with concept schemes",
        })
      )
        )
      );

      await expect(
        ontologyService.deleteTaxonomy("tax-123")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 422,
        detail: expect.stringContaining("concept schemes"),
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

      server.use(
        rest.get("*/api/schemes", (req, res, ctx) => res(ctx.json(mockSchemes)))
      );

      const result = await ontologyService.listSchemes();

      expect(result).toEqual(mockSchemes);
      expect(result.items).toHaveLength(2);
    });

    it("filters schemes by taxonomy_id via query params", async () => {
      const mockSchemes = createListSchemes([
        createConceptScheme({ id: "scheme-1", taxonomy_id: "tax-123" }),
      ]);

      server.use(
        rest.get("*/api/schemes", (req, res, ctx) => {
          const url = new URL(req.url);
          if (url.searchParams.get("taxonomy_id") === "tax-123") {
            return res(ctx.json(mockSchemes));
          }
          return res(ctx.json(createListSchemes([])));
        })
      );

      const result = await ontologyService.listSchemes("tax-123");

      expect(result.items).toHaveLength(1);
      expect(result.items[0].taxonomy_id).toBe("tax-123");
    });

    it("throws ApiError on 500 from listSchemes", async () => {
      server.use(
        rest.get("*/api/schemes", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
          detail: "Internal server error",
        })
      )
        )
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

      server.use(
        rest.get("*/api/schemes/scheme-123", (req, res, ctx) => res(ctx.json(mockScheme)))
      );

      const result = await ontologyService.getScheme("scheme-123");

      expect(result).toEqual(mockScheme);
    });

    it("throws ApiError with 404 on getScheme with non-existent ID", async () => {
      server.use(
        rest.get("*/api/schemes/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Concept scheme not found",
        })
      )
        )
      );

      await expect(
        ontologyService.getScheme("not-found")
      ).rejects.toMatchObject({
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
        rest.post("*/api/taxonomies/tax-123/schemes", (req, res, ctx) =>
          res(ctx.json(mockResponse))
        )
      );

      const result = await ontologyService.createScheme(
        "tax-123",
        createRequest
      );

      expect(result).toEqual(mockResponse);
      expect(result.taxonomy_id).toBe("tax-123");
    });

    it("throws ApiError with 404 on createScheme with non-existent taxonomy", async () => {
      const createRequest = createConceptSchemeCreateRequest();

      server.use(
        rest.post("*/api/taxonomies/not-found/schemes", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Taxonomy not found",
        })
      )
        )
      );

      await expect(
        ontologyService.createScheme("not-found", createRequest)
      ).rejects.toMatchObject({
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

      server.use(
        rest.put("*/api/schemes/scheme-123", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.updateScheme(
        "scheme-123",
        updateRequest
      );

      expect(result.title).toBe("Updated Scheme");
    });
  });

  describe("deleteScheme", () => {
    it("deletes scheme via DELETE /api/schemes/:id", async () => {
      server.use(
        rest.delete("*/api/schemes/scheme-123", (req, res, ctx) =>
          res(ctx.status(204))
        )
      );

      await expect(
        ontologyService.deleteScheme("scheme-123")
      ).resolves.toBeDefined();
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

      server.use(
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses)))
      );

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
        rest.get("*/api/classes", (req, res, ctx) => {
          const url = new URL(req.url);
          const hasScheme = url.searchParams.get("concept_scheme_id") === "scheme-123";
          const hasParent = url.searchParams.get("parent_class_id") === "class-parent";

          if (hasScheme && hasParent) {
            return res(ctx.json(mockClasses));
          }
          return res(ctx.json(createListClasses([])));
        })
      );

      const result = await ontologyService.listClasses({
        concept_scheme_id: "scheme-123",
        parent_class_id: "class-parent",
      });

      expect(result.items).toHaveLength(1);
    });

    it("throws ApiError on 500 from listClasses", async () => {
      server.use(
        rest.get("*/api/classes", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
          detail: "Internal server error",
        })
      )
        )
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

      server.use(
        rest.get("*/api/classes/class-123", (req, res, ctx) => res(ctx.json(mockClass)))
      );

      const result = await ontologyService.getClass("class-123");

      expect(result).toEqual(mockClass);
    });

    it("throws ApiError with 404 on getClass with non-existent ID", async () => {
      server.use(
        rest.get("*/api/classes/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Class not found",
        })
      )
        )
      );

      await expect(
        ontologyService.getClass("not-found")
      ).rejects.toMatchObject({
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
        rest.post("*/api/schemes/scheme-123/classes", (req, res, ctx) =>
          res(ctx.json(mockResponse))
        )
      );

      const result = await ontologyService.createClass(
        "scheme-123",
        createRequest
      );

      expect(result.concept_scheme_id).toBe("scheme-123");
    });
  });

  describe("updateClass", () => {
    it("updates class from PUT /api/classes/:id", async () => {
      const updateRequest = { title: "Updated Dog" };
      const mockResponse = createClass({
        id: "class-123",
        title: "Updated Dog",
      });

      server.use(
        rest.put("*/api/classes/class-123", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.updateClass(
        "class-123",
        updateRequest
      );

      expect(result.title).toBe("Updated Dog");
    });
  });

  describe("moveClass", () => {
    it("moves class to new concept scheme from POST /api/classes/:id/move", async () => {
      const moveRequest = { target_scheme_id: "scheme-new" };
      const mockResponse = createClass({
        id: "class-123",
        concept_scheme_id: "scheme-new",
      });

      server.use(
        rest.post("*/api/classes/class-123/move", (req, res, ctx) =>
          res(ctx.json(mockResponse))
        )
      );

      const result = await ontologyService.moveClass("class-123", moveRequest);

      expect(result.concept_scheme_id).toBe("scheme-new");
    });

    it("throws ApiError with 400 on moveClass with invalid scheme", async () => {
      const moveRequest = { target_scheme_id: "invalid" };

      server.use(
        rest.post("*/api/classes/class-123/move", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
          detail: "Target scheme not found",
        })
      )
        )
      );

      await expect(
        ontologyService.moveClass("class-123", moveRequest)
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("deleteClass", () => {
    it("deletes class via DELETE /api/classes/:id", async () => {
      server.use(
        rest.delete("*/api/classes/class-123", (req, res, ctx) =>
          res(ctx.status(204))
        )
      );

      await expect(
        ontologyService.deleteClass("class-123")
      ).resolves.toBeDefined();
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

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals)))
      );

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
        rest.get("*/api/individuals", (req, res, ctx) => {
          const url = new URL(req.url);
          if (url.searchParams.get("class_id") === "class-dog") {
            return res(ctx.json(mockIndividuals));
          }
          return res(ctx.json(createListIndividuals([])));
        })
      );

      const result = await ontologyService.listIndividuals({
        class_id: "class-dog",
      });

      expect(result.items).toHaveLength(1);
    });

    it("throws ApiError on 500 from listIndividuals", async () => {
      server.use(
        rest.get("*/api/individuals", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
          detail: "Internal server error",
        })
      )
        )
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

      server.use(
        rest.get("*/api/individuals/ind-123", (req, res, ctx) => res(ctx.json(mockIndividual)))
      );

      const result = await ontologyService.getIndividual("ind-123");

      expect(result).toEqual(mockIndividual);
    });

    it("throws ApiError with 404 on getIndividual with non-existent ID", async () => {
      server.use(
        rest.get("*/api/individuals/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Individual not found",
        })
      )
        )
      );

      await expect(
        ontologyService.getIndividual("not-found")
      ).rejects.toMatchObject({
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

      server.use(
        rest.post("*/api/individuals", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.createIndividual(createRequest);

      expect(result.id).toBe("ind-999");
      expect(result.class_ids).toContain("class-dog");
    });

    it("throws ApiError with 400 on createIndividual with invalid class", async () => {
      const createRequest = createIndividualCreateRequest({
        class_ids: ["invalid-class"],
      });

      server.use(
        rest.post("*/api/individuals", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
          detail: "One or more classes not found",
        })
      )
        )
      );

      await expect(
        ontologyService.createIndividual(createRequest)
      ).rejects.toMatchObject({
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

      server.use(
        rest.put("*/api/individuals/ind-123", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.updateIndividual(
        "ind-123",
        updateRequest
      );

      expect(result.title).toBe("Updated Fido");
    });
  });

  describe("deleteIndividual", () => {
    it("deletes individual via DELETE /api/individuals/:id", async () => {
      server.use(
        rest.delete("*/api/individuals/ind-123", (req, res, ctx) =>
          res(ctx.status(204))
        )
      );

      await expect(
        ontologyService.deleteIndividual("ind-123")
      ).resolves.toBeDefined();
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
        rest.post("*/api/individuals/ind-123/classes", (req, res, ctx) =>
          res(ctx.json(mockResponse))
        )
      );

      const result = await ontologyService.addParentClass(
        "ind-123",
        classRequest
      );

      expect(result.class_ids).toContain("class-new");
    });

    it("throws ApiError with 404 on addParentClass with non-existent individual", async () => {
      const classRequest = { class_id: "class-new" };

      server.use(
        rest.post("*/api/individuals/not-found/classes", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Individual not found",
        })
      )
        )
      );

      await expect(
        ontologyService.addParentClass("not-found", classRequest)
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });

  describe("removeParentClass", () => {
    it("removes parent class from individual via DELETE /api/individuals/:individualId/classes/:classId", async () => {
      server.use(
        rest.delete("*/api/individuals/ind-123/classes/class-old", (req, res, ctx) =>
          res(ctx.status(204))
        )
      );

      await expect(
        ontologyService.removeParentClass("ind-123", "class-old")
      ).resolves.toBeDefined();
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
        rest.put("*/api/individuals/ind-123/classes", (req, res, ctx) =>
          res(ctx.json(mockResponse))
        )
      );

      const result = await ontologyService.reorderIndividualClasses(
        "ind-123",
        reorderRequest
      );

      expect(result.class_ids).toEqual(["class-2", "class-1", "class-3"]);
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

      server.use(
        rest.get("*/api/properties", (req, res, ctx) => res(ctx.json(mockProperties)))
      );

      const result = await ontologyService.listProperties();

      expect(result.items).toHaveLength(2);
    });

    it("filters properties by is_relevant", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({ id: "prop-1", title: "Important" }),
      ]);

      server.use(
        rest.get("*/api/properties", (req, res, ctx) => {
          const url = new URL(req.url);
          if (url.searchParams.get("is_relevant") === "true") {
            return res(ctx.json(mockProperties));
          }
          return res(ctx.json(createListProperties([])));
        })
      );

      const result = await ontologyService.listProperties(true);

      expect(result.items).toHaveLength(1);
    });

    it("throws ApiError on 500 from listProperties", async () => {
      server.use(
        rest.get("*/api/properties", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
          detail: "Internal server error",
        })
      )
        )
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

      server.use(
        rest.get("*/api/properties/prop-123", (req, res, ctx) => res(ctx.json(mockProperty)))
      );

      const result = await ontologyService.getProperty("prop-123");

      expect(result).toEqual(mockProperty);
    });

    it("throws ApiError with 404 on getProperty with non-existent ID", async () => {
      server.use(
        rest.get("*/api/properties/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Property not found",
        })
      )
        )
      );

      await expect(
        ontologyService.getProperty("not-found")
      ).rejects.toMatchObject({
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

      server.use(
        rest.post("*/api/properties", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.createProperty(createRequest);

      expect(result.id).toBe("prop-999");
      expect(result.title).toBe("Color");
    });

    it("throws ApiError with 400 on createProperty with invalid data", async () => {
      const createRequest = createPropertyDefinitionCreateRequest({
        title: "",
      });

      server.use(
        rest.post("*/api/properties", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
          detail: "Title cannot be empty",
        })
      )
        )
      );

      await expect(
        ontologyService.createProperty(createRequest)
      ).rejects.toMatchObject({
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

      server.use(
        rest.put("*/api/properties/prop-123", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.updateProperty(
        "prop-123",
        updateRequest
      );

      expect(result.title).toBe("Updated Color");
    });
  });

  describe("deleteProperty", () => {
    it("deletes property via DELETE /api/properties/:id", async () => {
      server.use(
        rest.delete("*/api/properties/prop-123", (req, res, ctx) =>
          res(ctx.status(204))
        )
      );

      await expect(
        ontologyService.deleteProperty("prop-123")
      ).resolves.toBeDefined();
    });

    it("throws ApiError with 422 on deleteProperty with dependent relationships", async () => {
      server.use(
        rest.delete("*/api/properties/prop-123", (req, res, ctx) =>
          res(
        ctx.status(422),
        ctx.json({
          detail: "Cannot delete property with existing relationships",
        })
      )
        )
      );

      await expect(
        ontologyService.deleteProperty("prop-123")
      ).rejects.toMatchObject({
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

      server.use(
        rest.get("*/api/relationships", (req, res, ctx) => res(ctx.json(mockRelationships)))
      );

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
        rest.get("*/api/relationships", (req, res, ctx) => {
          const url = new URL(req.url);
          const hasSource = url.searchParams.get("source_id") === "class-1";
          const hasTarget = url.searchParams.get("target_id") === "class-2";
          const hasProperty = url.searchParams.get("property_id") === "prop-123";

          if (hasSource && hasTarget && hasProperty) {
            return res(ctx.json(mockRelationships));
          }
          return res(ctx.json(createListRelationships([])));
        })
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
        rest.get("*/api/relationships", (req, res, ctx) =>
          res(
        ctx.status(500),
        ctx.json({
          detail: "Internal server error",
        })
      )
        )
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
        rest.get("*/api/relationships/rel-123", (req, res, ctx) =>
          res(ctx.json(mockRelationship))
        )
      );

      const result = await ontologyService.getRelationship("rel-123");

      expect(result).toEqual(mockRelationship);
    });

    it("throws ApiError with 404 on getRelationship with non-existent ID", async () => {
      server.use(
        rest.get("*/api/relationships/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Relationship not found",
        })
      )
        )
      );

      await expect(
        ontologyService.getRelationship("not-found")
      ).rejects.toMatchObject({
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

      server.use(
        rest.post("*/api/relationships", (req, res, ctx) => res(ctx.json(mockResponse)))
      );

      const result = await ontologyService.createRelationship(createRequest);

      expect(result.id).toBe("rel-999");
    });

    it("throws ApiError with 400 on createRelationship with invalid classes", async () => {
      const createRequest = createRelationshipCreateRequest({
        source_id: "invalid",
      });

      server.use(
        rest.post("*/api/relationships", (req, res, ctx) =>
          res(
        ctx.status(400),
        ctx.json({
          detail: "Source class not found",
        })
      )
        )
      );

      await expect(
        ontologyService.createRelationship(createRequest)
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 400,
      });
    });
  });

  describe("deleteRelationship", () => {
    it("deletes relationship via DELETE /api/relationships/:id", async () => {
      server.use(
        rest.delete("*/api/relationships/rel-123", (req, res, ctx) =>
          res(ctx.status(204))
        )
      );

      await expect(
        ontologyService.deleteRelationship("rel-123")
      ).resolves.toBeDefined();
    });

    it("throws ApiError with 404 on deleteRelationship with non-existent ID", async () => {
      server.use(
        rest.delete("*/api/relationships/not-found", (req, res, ctx) =>
          res(
        ctx.status(404),
        ctx.json({
          detail: "Relationship not found",
        })
      )
        )
      );

      await expect(
        ontologyService.deleteRelationship("not-found")
      ).rejects.toMatchObject({
        name: "ApiError",
        status: 404,
      });
    });
  });
});
