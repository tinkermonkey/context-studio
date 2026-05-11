import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rest } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { IndividualDrawer } from "../IndividualDrawer";
import {
  createListIndividuals,
  createIndividual,
  createListClasses,
  createClass,
} from "@/api/services/__tests__/fixtures/ontology.fixtures";

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

describe("IndividualDrawer - Mutation UI and Workflows", () => {
  describe("edit form for title and description mutations", () => {
    it("renders editable title input for updates", async () => {
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
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-drawer-name-input")).toBeInTheDocument();
      });

      const titleInput = screen.getByTestId("individual-drawer-name-input") as HTMLInputElement;
      expect(titleInput.value).toBe("Test Individual");
    });

    it("renders editable description input for updates", async () => {
      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          description: "A test description",
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
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        const descInput = screen.getByTestId(
          "individual-drawer-description-input",
        ) as HTMLTextAreaElement;
        expect(descInput.value).toBe("A test description");
      });
    });

    it("allows changing title value", async () => {
      const user = userEvent.setup();

      const mockIndividuals = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Original Title",
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
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByDisplayValue("Original Title")).toBeInTheDocument();
      });

      const titleInput = screen.getByTestId(
        "individual-drawer-name-input",
      ) as HTMLInputElement;
      await user.clear(titleInput);
      await user.type(titleInput, "New Title");

      expect(titleInput.value).toBe("New Title");
    });
  });

  describe("add class mutation UI", () => {
    it("renders class typeahead input for adding classes", async () => {
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
        createClass({
          id: "class-employee",
          title: "Employee",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-typeahead")).toBeInTheDocument();
      });

      const typeaheadInput = screen.getByTestId("individual-class-typeahead") as HTMLInputElement;
      expect(typeaheadInput).not.toBeDisabled();
    });

    it("shows available classes when typing in typeahead", async () => {
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
        createClass({
          id: "class-employee",
          title: "Employee",
        }),
      ]);

      server.use(
        rest.get("*/api/individuals", (req, res, ctx) => res(ctx.json(mockIndividuals))),
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-typeahead")).toBeInTheDocument();
      });

      const typeaheadInput = screen.getByTestId("individual-class-typeahead");
      await user.click(typeaheadInput);
      await user.type(typeaheadInput, "Employee");

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-option-class-employee")).toBeInTheDocument();
      });
    });
  });

  describe("remove class mutation UI", () => {
    it("renders remove buttons for each selected class", async () => {
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
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
      });

      expect(screen.getByTestId("individual-class-remove-class-person")).toBeInTheDocument();
      expect(screen.getByTestId("individual-class-remove-class-employee")).toBeInTheDocument();
    });

  });

  describe("reorder class mutations UI", () => {
    it("renders move up/down buttons for classes", async () => {
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
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Employee")).toBeInTheDocument();
      });

      // First class should have move-down but not move-up
      expect(
        screen.getByTestId("individual-class-move-down-class-person"),
      ).not.toBeDisabled();
      expect(screen.getByTestId("individual-class-move-up-class-person")).toBeDisabled();

      // Last class should have move-up but not move-down
      expect(
        screen.getByTestId("individual-class-move-up-class-employee"),
      ).not.toBeDisabled();
      expect(screen.getByTestId("individual-class-move-down-class-employee")).toBeDisabled();
    });

    it("disables move buttons when only one class exists", async () => {
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
        rest.get("*/api/classes", (req, res, ctx) => res(ctx.json(mockClasses))),
        rest.get("*/api/individuals/*/inherited-properties", (req, res, ctx) =>
          res(ctx.json({ items: [], total: 0, limit: 10, offset: 0 }))
        ),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
      });

      expect(screen.getByTestId("individual-class-move-up-class-person")).toBeDisabled();
      expect(screen.getByTestId("individual-class-move-down-class-person")).toBeDisabled();
    });
  });
});
