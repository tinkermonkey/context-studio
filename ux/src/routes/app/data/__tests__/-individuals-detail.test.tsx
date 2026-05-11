import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import {
  createListIndividuals,
  createIndividual,
  createListClasses,
  createClass,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";
import { IndividualDrawer } from "@/components/ontology/IndividualDrawer";

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

describe("Individual Detail Page (Drawer Component)", () => {
  // ========================================================================
  // Drawer Closed State
  // ========================================================================
  describe("drawer closed state", () => {
    it("does not render drawer when individualId is null", () => {
      const mockIndividuals = createListIndividuals([]);
      const mockClasses = createListClasses([]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses)))
      );

      const { container } = render(<IndividualDrawer individualId={null} onClose={() => {}} />);

      expect(
        container.querySelector('[data-testid="individual-detail-page"]'),
      ).not.toBeInTheDocument();
    });
  });

  // ========================================================================
  // Drawer Populated State
  // ========================================================================
  describe("drawer populated state", () => {
    it("displays individual details when individualId is provided", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "John Doe",
          description: "Test description",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/ind-001/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByDisplayValue("John Doe")).toBeInTheDocument();
      });
    });

    it("displays read-only ID field", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        const idInput = screen.getByTestId("individual-drawer-id") as HTMLInputElement;
        expect(idInput.value).toBe("ind-001");
        expect(idInput.disabled).toBe(true);
      });
    });

    it("displays editable name input field", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Original Title",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        const nameInput = screen.getByTestId("individual-drawer-name-input") as HTMLInputElement;
        expect(nameInput.value).toBe("Original Title");
      });
    });

    it("displays editable description textarea", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          description: "This is a test description",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        const descInput = screen.getByTestId(
          "individual-drawer-description-input",
        ) as HTMLTextAreaElement;
        expect(descInput.value).toBe("This is a test description");
      });
    });

    it("displays class membership panel with class chips", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-person", "class-employee"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
        createClass({
          id: "class-employee",
          title: "Employee",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Class Membership")).toBeInTheDocument();
      });

      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.getByText("Employee")).toBeInTheDocument();
    });

    it("displays class remove buttons with correct testids", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-person", "class-employee"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
        createClass({
          id: "class-employee",
          title: "Employee",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-remove-class-person")).toBeInTheDocument();
        expect(screen.getByTestId("individual-class-remove-class-employee")).toBeInTheDocument();
      });
    });

    it("displays class typeahead input for adding classes", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-typeahead")).toBeInTheDocument();
      });
    });

    it("displays inherited properties panel", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Inherited Properties")).toBeInTheDocument();
      });
    });

    it("displays related individuals panel", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "John Doe",
          class_ids: ["class-person"],
        }),
        createIndividual({
          id: "ind-002",
          title: "Jane Doe",
          class_ids: ["class-person"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-person",
          title: "Person",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Related Individuals")).toBeInTheDocument();
      });
    });

    it("displays close button with correct testid", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-drawer-close-button")).toBeInTheDocument();
        expect(screen.getByTestId("individual-drawer-close-button")).toHaveRole("button");
      });
    });
  });

  // ========================================================================
  // Drawer Error State
  // ========================================================================
  describe("drawer error state", () => {
    it("handles error loading inherited properties gracefully", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-123"],
        }),
      ]);

      const mockClasses = createListClasses([
        createClass({
          id: "class-123",
          title: "TestClass",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/individuals/ind-001", (req, res, ctx) => res(ctx.json(mockIndividuals.items[0]))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.status(500), ctx.json({ detail: "Server error" })),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Inherited Properties")).toBeInTheDocument();
      });
    });
  });
});
