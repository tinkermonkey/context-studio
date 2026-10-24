import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListClasses,
  createClass,
  createListSchemes,
  createConceptScheme,
  createListTaxonomies,
  createListProperties,
  createListRelationships,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { serverSideList, pageRequests } from "@/test/serverSideList";
import { ClassesPage } from "../classes";

const server = setupServer(
  http.get("*/api/taxonomies", () => HttpResponse.json(createListTaxonomies([]))),
  http.get("*/api/schemes", () => HttpResponse.json(createListSchemes([]))),
  http.get("*/api/properties", () => HttpResponse.json(createListProperties([]))),
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

type ClassFixture = ReturnType<typeof createClass>;

/** /api/classes behaving like the server (q, ids, concept_scheme_id, paging). */
function serverSideClasses(all: ClassFixture[], requests: URLSearchParams[] = []) {
  return serverSideList("/api/classes", all, requests, {
    filters: { concept_scheme_id: (c, value) => c.concept_scheme_id === value },
  });
}

describe("Classes Schema Page", () => {
  // ========================================================================
  // Loading State
  // ========================================================================
  describe("loading state", () => {
    it("displays loading skeleton state with 5 skeleton rows matching table layout", async () => {
      server.use(
        http.get("*/api/classes", async () => {
          await new Promise((resolve) => setTimeout(resolve, 100));
          return HttpResponse.json(createListClasses([]));
        }),
        http.get("*/api/schemes", () => HttpResponse.json(createListSchemes([]))),
      );

      const { container } = render(<ClassesPage />);

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
        http.get("*/api/classes", () =>
          HttpResponse.json({ detail: "Internal server error" }, { status: 500 }),
        ),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load classes/i)).toBeInTheDocument();
      });

      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // Empty State
  // ========================================================================
  describe("empty state", () => {
    it("displays empty state copy when no classes exist", async () => {
      server.use(http.get("*/api/classes", () => HttpResponse.json(createListClasses([]))));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("No classes yet")).toBeInTheDocument();
        expect(
          screen.getByText("Classes are the types your individuals will conform to."),
        ).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Populated State
  // ========================================================================
  describe("populated state", () => {
    it("displays table with classes when data loads", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
          description: "A person entity",
        }),
        createClass({
          id: "class-2",
          title: "Company",
          description: "A company entity",
        }),
      ]);

      server.use(http.get("*/api/classes", () => HttpResponse.json(mockClasses)));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
        expect(screen.getByText("Company")).toBeInTheDocument();
      });
    });

    it("displays mono ID in first column of table rows", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(http.get("*/api/classes", () => HttpResponse.json(mockClasses)));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestClass")).toBeInTheDocument();
      });

      // The identifier cell renders the id truncated to 8 chars ("class-12")
      // in a mono-font span, no longer a <code> element.
      const monoId = screen.getByText("class-12");
      expect(monoId.tagName.toLowerCase()).toBe("span");
      expect(monoId).toHaveStyle({ fontFamily: "var(--font-mono)" });
    });

    it("displays description column with em-dash placeholder when empty", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "TestClass",
          description: null,
        }),
      ]);

      server.use(http.get("*/api/classes", () => HttpResponse.json(mockClasses)));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("TestClass")).toBeInTheDocument();
      });

      const cells = screen.getAllByText("—");
      expect(cells.length).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Filtered State
  // ========================================================================
  describe("filtered state", () => {
    it("sends the search text to the server as q and shows only the matches", async () => {
      const requests: URLSearchParams[] = [];
      server.use(
        serverSideClasses(
          [
            createClass({ id: "class-1", title: "Person" }),
            createClass({ id: "class-2", title: "Company" }),
            createClass({ id: "class-3", title: "Location" }),
          ],
          requests,
        ),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Location")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i);
      await userEvent.type(searchInput, "Person");

      await waitFor(() => {
        expect(screen.queryByText("Company")).not.toBeInTheDocument();
      });
      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.queryByText("Location")).not.toBeInTheDocument();
      const last = pageRequests(requests).at(-1)!;
      expect(last.get("q")).toBe("Person");
      expect(last.get("offset")).toBe("0");
    });

    it("clears filter when search term is removed", async () => {
      const requests: URLSearchParams[] = [];
      server.use(
        serverSideClasses(
          [
            createClass({ id: "class-1", title: "Person" }),
            createClass({ id: "class-2", title: "Company" }),
          ],
          requests,
        ),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText(/search/i) as HTMLInputElement;
      await userEvent.type(searchInput, "Company");

      await waitFor(() => {
        expect(screen.queryByText("Person")).not.toBeInTheDocument();
      });

      await userEvent.clear(searchInput);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
      });
      expect(screen.getByText("Company")).toBeInTheDocument();
      expect(pageRequests(requests).at(-1)!.has("q")).toBe(false);
    });

    it("sends the domain filter as concept_scheme_id", async () => {
      const requests: URLSearchParams[] = [];
      server.use(
        serverSideClasses(
          [
            createClass({ id: "class-1", title: "Person", concept_scheme_id: "scheme-1" }),
            createClass({ id: "class-2", title: "Rock", concept_scheme_id: "scheme-2" }),
          ],
          requests,
        ),
        http.get("*/api/schemes", () =>
          HttpResponse.json(
            createListSchemes([
              createConceptScheme({ id: "scheme-1", title: "People" }),
              createConceptScheme({ id: "scheme-2", title: "Geology" }),
            ]),
          ),
        ),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Rock")).toBeInTheDocument();
      });
      await userEvent.click(screen.getByRole("radio", { name: "Geology" }));

      await waitFor(() => {
        expect(screen.queryByText("Person")).not.toBeInTheDocument();
      });
      expect(pageRequests(requests).at(-1)!.get("concept_scheme_id")).toBe("scheme-2");
    });
  });

  // ========================================================================
  // Server-side pagination
  // ========================================================================
  describe("server-side pagination", () => {
    const manyClasses = Array.from({ length: 120 }, (_, i) =>
      createClass({ id: `class-${i}`, title: `Class ${String(i).padStart(3, "0")}` }),
    );

    it("requests the first page newest-first and shows the server total", async () => {
      const requests: URLSearchParams[] = [];
      server.use(serverSideClasses(manyClasses, requests));

      render(<ClassesPage />);

      const pager = await screen.findByTestId("list-pager");
      expect(pager).toHaveClass("list-pager");
      expect(pager).toHaveAttribute("role", "navigation");
      expect(pager).toHaveAttribute("aria-label", "Pagination");
      expect(screen.getByTestId("list-pager-range")).toHaveTextContent("1–50 of 120");

      const first = pageRequests(requests)[0];
      expect(first.get("limit")).toBe("50");
      expect(first.get("offset")).toBe("0");
      expect(first.get("sort_by")).toBe("created_at");
      expect(first.get("sort_order")).toBe("desc");
    });

    it("requests the next page with an offset when Next is clicked", async () => {
      const requests: URLSearchParams[] = [];
      server.use(serverSideClasses(manyClasses, requests));

      render(<ClassesPage />);

      await screen.findByText("Class 000");
      await userEvent.click(screen.getByTestId("list-pager-next"));

      await waitFor(() => {
        expect(screen.getByTestId("list-pager-range")).toHaveTextContent("51–100 of 120");
      });
      expect(pageRequests(requests).at(-1)!.get("offset")).toBe("50");
      expect(screen.getByText("Class 050")).toBeInTheDocument();
      expect(screen.queryByText("Class 000")).not.toBeInTheDocument();
    });

    it("requests a larger page when the page size changes", async () => {
      const requests: URLSearchParams[] = [];
      server.use(serverSideClasses(manyClasses, requests));

      render(<ClassesPage />);

      await screen.findByText("Class 000");
      await userEvent.click(screen.getByRole("radio", { name: "250" }));

      await waitFor(() => {
        expect(screen.getByTestId("list-pager-range")).toHaveTextContent("1–120 of 120");
      });
      const last = pageRequests(requests).at(-1)!;
      expect(last.get("limit")).toBe("250");
      expect(last.get("offset")).toBe("0");
    });

    it("sorts server-side when the Title header is clicked", async () => {
      const requests: URLSearchParams[] = [];
      server.use(serverSideClasses(manyClasses, requests));

      render(<ClassesPage />);

      await screen.findByText("Class 000");
      const header = screen.getByRole("columnheader", { name: /title/i });
      await userEvent.click(header);

      await waitFor(() => {
        expect(pageRequests(requests).at(-1)!.get("sort_by")).toBe("title");
      });
      expect(pageRequests(requests).at(-1)!.get("sort_order")).toBe("asc");
    });

    it("resolves parent class titles with an ids lookup for the page", async () => {
      const requests: URLSearchParams[] = [];
      const parent = createClass({ id: "parent-1", title: "Organism" });
      const child = createClass({ id: "child-1", title: "Animal", parent_class_id: "parent-1" });
      server.use(
        http.get("*/api/classes", ({ request }) => {
          const params = new URL(request.url).searchParams;
          requests.push(params);
          // The parent is NOT on the page; only an ids lookup returns it.
          const items = params.getAll("ids").length ? [parent] : [child];
          return HttpResponse.json(createListClasses(items));
        }),
      );

      render(<ClassesPage />);

      await waitFor(() => {
        expect(screen.getByText("Organism")).toBeInTheDocument();
      });
      const lookup = requests.find((p) => p.getAll("ids").length > 0)!;
      expect(lookup.getAll("ids")).toEqual(["parent-1"]);
    });

    it("reads the tab counts from limit=1 requests", async () => {
      const requests: URLSearchParams[] = [];
      server.use(serverSideClasses(manyClasses, requests));

      render(<ClassesPage />);

      await waitFor(() => {
        expect(requests.some((p) => p.get("limit") === "1")).toBe(true);
      });
    });
  });

  // ========================================================================
  // Partial State
  // ========================================================================
  describe("partial state", () => {
    it("displays classes table even when schemes query fails", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
          concept_scheme_id: "scheme-1",
        }),
        createClass({
          id: "class-2",
          title: "Company",
          concept_scheme_id: "scheme-1",
        }),
      ]);

      server.use(
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/schemes", () =>
          HttpResponse.json({ detail: "Failed to load schemes" }, { status: 500 }),
        ),
      );

      render(<ClassesPage />);

      // Verify error banner appears for schemes failure
      await waitFor(() => {
        expect(screen.getByText(/Failed to load domains/i)).toBeInTheDocument();
      });

      // Verify classes table still renders despite schemes error
      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.getByText("Company")).toBeInTheDocument();

      // Verify retry button is available for schemes
      expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    });

    it("can retry schemes query independently when partial state occurs", async () => {
      const mockClasses = createListClasses([
        createClass({
          id: "class-1",
          title: "Person",
          concept_scheme_id: "scheme-1",
        }),
      ]);

      const mockSchemes = createListSchemes([
        createConceptScheme({ id: "scheme-1", title: "People Domain" }),
      ]);

      let schemesCallCount = 0;

      server.use(
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/schemes", ({ request }) => {
          // The limit=1 tab-count request is not the page's scheme lookup.
          if (new URL(request.url).searchParams.get("limit") === "1") {
            return HttpResponse.json(mockSchemes);
          }
          schemesCallCount++;
          if (schemesCallCount === 1) {
            return HttpResponse.json({ detail: "Failed to load schemes" }, { status: 500 });
          }
          return HttpResponse.json(mockSchemes);
        }),
      );

      render(<ClassesPage />);

      // Verify initial error state
      await waitFor(() => {
        expect(screen.getByText(/Failed to load domains/i)).toBeInTheDocument();
      });

      // Verify class is visible
      expect(screen.getByText("Person")).toBeInTheDocument();

      // Click retry and verify recovery
      const retryButtons = screen.getAllByRole("button", { name: /retry/i });
      const schemesRetryButton = retryButtons[0]; // First retry button is for schemes error
      await userEvent.click(schemesRetryButton);

      // Wait for schemes to load successfully
      await waitFor(() => {
        // Error banner should disappear
        expect(screen.queryByText(/Failed to load domains/i)).not.toBeInTheDocument();
        // Scheme name should now resolve in the Scheme column chip for the row.
        // "People Domain" also appears in the domain filter (SegmentedControl),
        // so scope the assertion to the row's scheme chip via its test id.
        const schemeChip = screen.getByTestId("class-domain-class-1");
        expect(schemeChip).toHaveTextContent("People Domain");
      });
    });
  });
});
