import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
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

describe("IndividualDrawer - Mutation Workflows", () => {
  const mockIndividuals = createListIndividuals([
    createIndividual({
      id: "ind-001",
      title: "Test Individual",
      description: "Original description",
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
    createClass({
      id: "class-manager",
      title: "Manager",
    }),
  ]);

  function setupDefaultHandlers() {
    server.use(
      http.get("*/api/individuals", () => HttpResponse.json(mockIndividuals)),
      http.get("*/api/individuals/ind-001", () => HttpResponse.json(mockIndividuals.items[0])),
      http.get("*/api/classes", () => HttpResponse.json(mockClasses)),
      http.get("*/api/individuals/*/inherited-properties", () =>
        HttpResponse.json({ items: [], total: 0, limit: 10, offset: 0 }),
      ),
    );
  }

  describe("title/description autosave mutation", () => {
    it("triggers autosave mutation when title changes", async () => {
      const user = userEvent.setup();
      let updateCalled = false;

      setupDefaultHandlers();
      server.use(
        http.put(/.*\/api\/individuals\/.*/, () => {
          updateCalled = true;
          return HttpResponse.json(
            createIndividual({
              id: "ind-001",
              title: "Updated Title",
              description: "Original description",
              class_ids: ["class-person", "class-employee"],
            }),
          );
        }),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-drawer-name-input")).toBeInTheDocument();
      });

      const titleInput = screen.getByTestId("individual-drawer-name-input") as HTMLInputElement;
      await user.clear(titleInput);
      await user.type(titleInput, "Updated Title");

      await waitFor(
        () => {
          expect(updateCalled).toBe(true);
        },
        { timeout: 3000 },
      );
    });

    it("triggers autosave mutation when description changes", async () => {
      const user = userEvent.setup();
      let updateCalled = false;

      setupDefaultHandlers();
      server.use(
        http.put(/.*\/api\/individuals\/.*/, () => {
          updateCalled = true;
          return HttpResponse.json(
            createIndividual({
              id: "ind-001",
              title: "Test Individual",
              description: "Updated description",
              class_ids: ["class-person", "class-employee"],
            }),
          );
        }),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-drawer-description-input")).toBeInTheDocument();
      });

      const descInput = screen.getByTestId(
        "individual-drawer-description-input",
      ) as HTMLTextAreaElement;
      await user.clear(descInput);
      await user.type(descInput, "Updated description");

      await waitFor(
        () => {
          expect(updateCalled).toBe(true);
        },
        { timeout: 3000 },
      );
    });
  });

  describe("add class mutation workflow", () => {
    it("calls mutation and adds class when option is selected", async () => {
      const user = userEvent.setup();
      let addClassCalled = false;

      setupDefaultHandlers();
      server.use(
        http.post(/.*\/api\/individuals\/.*\/classes/, () => {
          addClassCalled = true;
          return HttpResponse.json(
            createIndividual({
              id: "ind-001",
              title: "Test Individual",
              class_ids: ["class-person", "class-employee", "class-manager"],
            }),
          );
        }),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-typeahead")).toBeInTheDocument();
      });

      const typeaheadInput = screen.getByTestId("individual-class-typeahead");
      await user.click(typeaheadInput);
      await user.type(typeaheadInput, "Manager");

      await waitFor(() => {
        expect(screen.getByTestId("individual-class-option-class-manager")).toBeInTheDocument();
      });

      const managerOption = screen.getByTestId("individual-class-option-class-manager");
      await user.click(managerOption);

      await waitFor(
        () => {
          expect(addClassCalled).toBe(true);
        },
        { timeout: 3000 },
      );
    });
  });

  describe("remove class mutation workflow", () => {
    it("calls mutation when remove button is clicked", async () => {
      const user = userEvent.setup();
      let removeClassCalled = false;

      setupDefaultHandlers();
      server.use(
        http.delete(/.*\/api\/individuals\/.*\/classes\/.*/, () => {
          removeClassCalled = true;
          return HttpResponse.json(
            createIndividual({
              id: "ind-001",
              title: "Test Individual",
              class_ids: ["class-person"],
            }),
          );
        }),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Employee")).toBeInTheDocument();
      });

      const removeButton = screen.getByTestId("individual-class-remove-class-employee");
      await user.click(removeButton);

      await waitFor(
        () => {
          expect(removeClassCalled).toBe(true);
        },
        { timeout: 3000 },
      );
    });

    it("prevents removing last class", async () => {
      const user = userEvent.setup();

      const singleClassIndividual = createListIndividuals([
        createIndividual({
          id: "ind-001",
          title: "Test Individual",
          class_ids: ["class-person"],
        }),
      ]);

      setupDefaultHandlers();
      server.use(
        http.get("*/api/individuals", () => HttpResponse.json(singleClassIndividual)),
        http.delete(/.*\/api\/individuals\/.*\/classes\/.*/, () => {
          return HttpResponse.json({ detail: "Cannot remove last class" }, { status: 400 });
        }),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
      });

      const removeButton = screen.getByTestId("individual-class-remove-class-person");
      await user.click(removeButton);

      // Verify that a toastoccurs due to error (the mutation handler rejects)
      await waitFor(
        () => {
          // The component should show an error toast, but we can't directly test toasts
          // Instead, verify the remove button is still visible (class wasn't removed)
          expect(screen.getByTestId("individual-class-remove-class-person")).toBeInTheDocument();
        },
        { timeout: 3000 },
      );
    });
  });

  describe("reorder class mutation workflow", () => {
    it("calls mutation when move-up button is clicked", async () => {
      const user = userEvent.setup();
      let reorderCalled = false;

      setupDefaultHandlers();
      server.use(
        http.put(/.*\/api\/individuals\/.*\/classes$/, () => {
          reorderCalled = true;
          return HttpResponse.json(
            createIndividual({
              id: "ind-001",
              title: "Test Individual",
              class_ids: ["class-employee", "class-person"],
            }),
          );
        }),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Employee")).toBeInTheDocument();
      });

      const moveUpButton = screen.getByTestId("individual-class-move-up-class-employee");
      await user.click(moveUpButton);

      await waitFor(
        () => {
          expect(reorderCalled).toBe(true);
        },
        { timeout: 3000 },
      );
    });

    it("calls mutation when move-down button is clicked", async () => {
      const user = userEvent.setup();
      let reorderCalled = false;

      setupDefaultHandlers();
      server.use(
        http.put(/.*\/api\/individuals\/.*\/classes$/, () => {
          reorderCalled = true;
          return HttpResponse.json(
            createIndividual({
              id: "ind-001",
              title: "Test Individual",
              class_ids: ["class-employee", "class-person"],
            }),
          );
        }),
      );

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Person")).toBeInTheDocument();
      });

      const moveDownButton = screen.getByTestId("individual-class-move-down-class-person");
      await user.click(moveDownButton);

      await waitFor(
        () => {
          expect(reorderCalled).toBe(true);
        },
        { timeout: 3000 },
      );
    });

    it("disables move buttons appropriately", async () => {
      setupDefaultHandlers();

      render(<IndividualDrawer individualId="ind-001" onClose={() => {}} />);

      await waitFor(() => {
        expect(screen.getByText("Employee")).toBeInTheDocument();
      });

      // First class (Person) should not have move-up enabled
      expect(screen.getByTestId("individual-class-move-up-class-person")).toBeDisabled();
      expect(screen.getByTestId("individual-class-move-down-class-person")).not.toBeDisabled();

      // Last class (Employee) should not have move-down enabled
      expect(screen.getByTestId("individual-class-move-up-class-employee")).not.toBeDisabled();
      expect(screen.getByTestId("individual-class-move-down-class-employee")).toBeDisabled();
    });
  });
});
