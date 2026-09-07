import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
      );

      const { container } = render(<IndividualDrawer individualId={null} />);

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/ind-001/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getAllByText("John Doe").length).toBeGreaterThan(0);
      });
    });

    it("displays read-only ID field", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        const idInput = screen.getByTestId("individual-drawer-id") as HTMLInputElement;
        expect(idInput.value).toBe("ind-001");
        expect(idInput.disabled).toBe(true);
      });
    });

    it("displays editable name input field", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("individual-drawer-name-field-view")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("individual-drawer-name-field-view"));

      const nameInput = screen.getByTestId(
        "individual-drawer-name-field-input",
      ) as HTMLInputElement;
      expect(nameInput.value).toBe("Original Title");
    });

    it("displays editable description textarea", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("individual-drawer-description-field-view")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("individual-drawer-description-field-view"));

      const descInput = screen.getByTestId(
        "individual-drawer-description-field-input",
      ) as HTMLTextAreaElement;
      expect(descInput.value).toBe("This is a test description");
    });

    it("displays class membership panel with class chips", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-list")).toBeInTheDocument();
      });

      expect(screen.getByText("Person")).toBeInTheDocument();
      expect(screen.getByText("Employee")).toBeInTheDocument();
    });

    it("displays class remove buttons with correct testids", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-remove-class-person")).toBeInTheDocument();
        expect(screen.getByTestId("individual-class-remove-class-employee")).toBeInTheDocument();
      });
    });

    it("displays class typeahead input for adding classes", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-typeahead")).toBeInTheDocument();
      });
    });

    it("displays inherited properties panel", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("individual-properties-panel")).toBeInTheDocument();
      });
    });

    it("displays related individuals panel", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("related-individuals-panel")).toBeInTheDocument();
      });
    });

    it("renders the inspector actions region (autosave status)", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      // In edit mode the InlineInspector renders inspector-autosave-status in the actions slot.
      await waitFor(() => {
        expect(screen.getByTestId("inspector-autosave-status")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Drawer Error State
  // ========================================================================
  describe("drawer error state", () => {
    it("handles error loading inherited properties gracefully", async () => {
      const user = userEvent.setup();

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
        http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
        http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
        http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
        http.get("*/api/individuals/*/inherited-properties", () =>
          HttpResponse.json({ detail: "Server error" }, { status: 500 }),
        ),
      );

      render(<IndividualDrawer individualId="ind-001" />);

      await waitFor(() => {
        expect(screen.getByTestId("inline-inspector-edit-button")).toBeInTheDocument();
      });
      await user.click(screen.getByTestId("inline-inspector-edit-button"));

      await waitFor(() => {
        expect(screen.getByTestId("individual-properties-panel")).toBeInTheDocument();
      });
    });
  });
});
