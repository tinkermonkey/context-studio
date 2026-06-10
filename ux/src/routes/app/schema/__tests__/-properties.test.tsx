import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListProperties,
  createPropertyDefinition,
  createListTaxonomies,
  createListSchemes,
  createListClasses,
  createListRelationships,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { PropertiesPage } from "../properties";

const server = setupServer(
  http.get("*/api/taxonomies", () => HttpResponse.json(createListTaxonomies([]))),
  http.get("*/api/schemes", () => HttpResponse.json(createListSchemes([]))),
  http.get("*/api/classes", () => HttpResponse.json(createListClasses([]))),
  http.get("*/api/relationships", () => HttpResponse.json(createListRelationships([]))),
);

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

describe("Properties Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state with 5 skeleton rows matching table layout", async () => {
      server.use(
        http.get("*/api/properties", async () => {
          // Delay the response so we can capture loading state
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(createListProperties([]));
        }),
      );

      const { container } = render(<PropertiesPage />);

      // Verify skeleton rows are rendered before data arrives.
      // Skeletons now use the `.skeleton` class (shimmer is in CSS, not inline style).
      const skeletonElements = container.querySelectorAll(".skeleton");
      expect(skeletonElements.length).toBeGreaterThanOrEqual(5);
    });
  });

  // ========================================================================
  // Error State
  // ========================================================================
  describe("error state", () => {
    it("displays error banner with retry button when API fails", async () => {
      server.use(
        http.get("*/api/properties", () =>
          HttpResponse.json({ detail: "Internal server error" }, { status: 500 }),
        ),
      );

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load properties/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("retry button triggers refetch on error", async () => {
      let callCount = 0;

      server.use(
        http.get("*/api/properties", () => {
          callCount++;
          if (callCount === 1) {
            return HttpResponse.json({ detail: "Server error" }, { status: 500 });
          }
          return HttpResponse.json(createListProperties([]));
        }),
      );

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load properties/i)).toBeInTheDocument();
      });

      const retryButton = screen.getByRole("button", { name: /retry/i });
      await userEvent.click(retryButton);

      await waitFor(() => {
        expect(screen.queryByText(/Failed to load properties/i)).not.toBeInTheDocument();
      });

      expect(callCount).toBe(2);
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no properties exist", async () => {
      server.use(http.get("*/api/properties", () => HttpResponse.json(createListProperties([]))));

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText("No properties yet")).toBeInTheDocument();
        expect(
          screen.getByText("Property definitions are the named predicates used by relationships."),
        ).toBeInTheDocument();
      });
    });

    it("empty state displays action label button", async () => {
      server.use(http.get("*/api/properties", () => HttpResponse.json(createListProperties([]))));

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByTestId("empty-state-action")).toBeInTheDocument();
        expect(screen.getByTestId("empty-state-action")).toHaveTextContent("+ Add property");
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with properties when data loads", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({
          id: "prop-1",
          title: "Color",
          identifier: "color",
          description: "The color attribute",
        }),
        createPropertyDefinition({
          id: "prop-2",
          title: "Size",
          identifier: "size",
          description: "The size attribute",
        }),
      ]);

      server.use(http.get("*/api/properties", () => HttpResponse.json(mockProperties)));

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Color")).toBeInTheDocument();
        expect(screen.getByText("Size")).toBeInTheDocument();
      });
    });

    it("displays mono identifier in first column of table rows", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({
          id: "prop-123",
          title: "TestProp",
          identifier: "test_prop",
        }),
      ]);

      server.use(http.get("*/api/properties", () => HttpResponse.json(mockProperties)));

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestProp")).toBeInTheDocument();
      });

      // The first column for properties is the property `identifier` (not the
      // raw id), rendered in a mono-font span — no longer a <code> element.
      const monoId = screen.getByText("test_prop");
      expect(monoId.tagName.toLowerCase()).toBe("span");
      expect(monoId).toHaveStyle({ fontFamily: "var(--font-mono)" });
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({
          id: "prop-1",
          title: "TestProp",
          identifier: "test_prop",
          description: null,
        }),
      ]);

      server.use(http.get("*/api/properties", () => HttpResponse.json(mockProperties)));

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestProp")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Filtered State
  // ========================================================================
  describe("filtered state", () => {
    it("filters properties by search term and hides non-matching rows", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({
          id: "prop-1",
          title: "Color",
          identifier: "color",
        }),
        createPropertyDefinition({
          id: "prop-2",
          title: "Shape",
          identifier: "shape",
        }),
        createPropertyDefinition({
          id: "prop-3",
          title: "Size",
          identifier: "size",
        }),
      ]);

      server.use(http.get("*/api/properties", () => HttpResponse.json(mockProperties)));

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Color")).toBeInTheDocument();
        expect(screen.getByText("Shape")).toBeInTheDocument();
        expect(screen.getByText("Size")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "Color");

      expect(screen.getByText("Color")).toBeInTheDocument();
      expect(screen.queryByText("Shape")).not.toBeInTheDocument();
      expect(screen.queryByText("Size")).not.toBeInTheDocument();
    });

    it("clears filter when search term is removed", async () => {
      const mockProperties = createListProperties([
        createPropertyDefinition({
          id: "prop-1",
          title: "Color",
          identifier: "color",
        }),
        createPropertyDefinition({
          id: "prop-2",
          title: "Shape",
          identifier: "shape",
        }),
      ]);

      server.use(http.get("*/api/properties", () => HttpResponse.json(mockProperties)));

      render(<PropertiesPage />);

      await waitFor(() => {
        expect(screen.getByText("Color")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await userEvent.type(searchInput, "Color");

      expect(screen.queryByText("Shape")).not.toBeInTheDocument();

      await userEvent.clear(searchInput);

      expect(screen.getByText("Color")).toBeInTheDocument();
      expect(screen.getByText("Shape")).toBeInTheDocument();
    });
  });
});
