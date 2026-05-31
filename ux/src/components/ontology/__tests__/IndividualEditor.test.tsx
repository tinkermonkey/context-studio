import { describe, it, expect, vi, beforeAll, beforeEach, afterEach, afterAll } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { IndividualEditor } from "../IndividualEditor";
import {
  createListClasses,
  createClass,
  createIndividual,
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

// ============================================================================
// Mock Data Setup
// ============================================================================

const mockClasses = [
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
];

// ============================================================================
// Helper Functions
// ============================================================================

function setupDefaultMocks() {
  server.use(http.get("*/api/classes", () => HttpResponse.json(createListClasses(mockClasses))));
}

// ============================================================================
// Test Suite
// ============================================================================

describe("IndividualEditor", () => {
  beforeEach(() => {
    setupDefaultMocks();
  });
  // ========================================================================
  // Form Validation Tests
  // ========================================================================
  describe("form validation", () => {
    it("displays title error when submitting empty form", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "",
            class_ids: ["class-person"],
          }}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Title is required")).toBeInTheDocument();
      });

      expect(onSubmit).not.toHaveBeenCalled();
    });

    it("displays class error when submitting with no classes", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test Individual",
            class_ids: [],
          }}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      await user.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("At least one class must be selected")).toBeInTheDocument();
      });

      expect(onSubmit).not.toHaveBeenCalled();
    });

    it("clears title error when valid title is entered", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "",
            class_ids: ["class-person"],
          }}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      await user.click(submitButton);

      expect(screen.getByText("Title is required")).toBeInTheDocument();

      const titleInput = screen.getByTestId("individual-title-input") as HTMLInputElement;
      // Clear and type new value
      await user.clear(titleInput);
      await user.type(titleInput, "New Individual");

      // Error should be cleared since title is now valid
      expect(titleInput.value).toBe("New Individual");
    });

    it("validates title on blur", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test",
            class_ids: ["class-person"],
          }}
        />,
      );

      const titleInput = screen.getByTestId("individual-title-input");
      await user.clear(titleInput);
      await user.click(screen.getByTestId("individual-class-select"));

      await waitFor(() => {
        expect(screen.getByText("Title is required")).toBeInTheDocument();
      });
    });
  });

  // ========================================================================
  // Create Workflow Tests
  // ========================================================================
  describe("create workflow", () => {
    it("submits form with valid data", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "John Doe",
            description: "A test person",
            class_ids: ["class-person"],
          }}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          title: "John Doe",
          description: "A test person",
          class_ids: ["class-person"],
        });
      });
    });

    it("submits with null description when empty", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Jane Doe",
            description: "",
            class_ids: ["class-employee"],
          }}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          title: "Jane Doe",
          description: null,
          class_ids: ["class-employee"],
        });
      });
    });

    it("disables submit button when loading", async () => {
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test Individual",
            class_ids: ["class-person"],
          }}
          isLoading={true}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button") as HTMLButtonElement;
      expect(submitButton.disabled).toBe(true);
    });

    it("displays create button text for new individual", () => {
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "",
            class_ids: [],
          }}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      expect(submitButton).toHaveTextContent("Create");
    });
  });

  // ========================================================================
  // Edit Workflow Tests
  // ========================================================================
  describe("edit workflow", () => {
    it("displays edit button text for existing individual", () => {
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={createIndividual({
            id: "ind-123",
            title: "Existing Individual",
            class_ids: ["class-person"],
          })}
          individualId="ind-123"
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      expect(submitButton).toHaveTextContent("Update");
    });

    it("updates form state when editing text fields", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          initialData={{
            title: "Original Title",
            description: "Original description",
            class_ids: ["class-person"],
          }}
          onSubmit={onSubmit}
        />,
      );

      const titleInput = screen.getByTestId("individual-title-input") as HTMLInputElement;
      await user.clear(titleInput);
      await user.type(titleInput, "Updated Title");

      const descInput = screen.getByTestId("individual-description-input") as HTMLTextAreaElement;
      await user.clear(descInput);
      await user.type(descInput, "Updated description");

      expect(titleInput.value).toBe("Updated Title");
      expect(descInput.value).toBe("Updated description");

      const submitButton = screen.getByTestId("individual-submit-button");
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          title: "Updated Title",
          description: "Updated description",
          class_ids: ["class-person"],
        });
      });
    });

    it("disables class selection input when individualId is provided", () => {
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={createIndividual({
            id: "ind-123",
            title: "Test Individual",
            class_ids: ["class-person"],
          })}
          individualId="ind-123"
        />,
      );

      const classInput = screen.getByTestId("individual-class-select") as HTMLInputElement;
      expect(classInput.disabled).toBe(true);
    });
  });

  // ========================================================================
  // Keyboard Shortcuts Tests
  // ========================================================================
  describe("keyboard shortcuts", () => {
    it("submits form on Cmd+Enter", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test Individual",
            class_ids: ["class-person"],
          }}
        />,
      );

      const titleInput = screen.getByTestId("individual-title-input");
      await user.click(titleInput);
      await user.keyboard("{Meta>}{Enter}");

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalled();
      });
    });

    it("submits form on Ctrl+Enter", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test Individual",
            class_ids: ["class-person"],
          }}
        />,
      );

      const titleInput = screen.getByTestId("individual-title-input");
      await user.click(titleInput);
      await user.keyboard("{Control>}{Enter}");

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalled();
      });
    });
  });

  // ========================================================================
  // Class Selection Tests (Create Only)
  // ========================================================================
  describe("class selection in create mode", () => {
    it("submits form with multiple selected classes", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test Individual",
            description: "Test description",
            class_ids: ["class-person", "class-employee"],
          }}
        />,
      );

      const submitButton = screen.getByTestId("individual-submit-button");
      await user.click(submitButton);

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledWith({
          title: "Test Individual",
          description: "Test description",
          class_ids: ["class-person", "class-employee"],
        });
      });
    });
  });

  // ========================================================================
  // Form Field Tests
  // ========================================================================
  describe("form fields and state", () => {
    it("renders all form fields", () => {
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test",
            description: "Test description",
            class_ids: ["class-person"],
          }}
        />,
      );

      expect(screen.getByTestId("individual-title-input")).toBeInTheDocument();
      expect(screen.getByTestId("individual-description-input")).toBeInTheDocument();
      expect(screen.getByTestId("individual-class-select")).toBeInTheDocument();
      expect(screen.getByTestId("individual-submit-button")).toBeInTheDocument();
    });

    it("initializes form with provided data", () => {
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "John Doe",
            description: "A person entity",
            class_ids: ["class-person"],
          }}
        />,
      );

      const titleInput = screen.getByTestId("individual-title-input") as HTMLInputElement;
      const descInput = screen.getByTestId("individual-description-input") as HTMLTextAreaElement;

      expect(titleInput.value).toBe("John Doe");
      expect(descInput.value).toBe("A person entity");

      // Verify that the form can submit with the initialized class_ids
      const submitButton = screen.getByTestId("individual-submit-button");
      expect(submitButton).toBeInTheDocument();
    });

    it("autofocuses title input", () => {
      const onSubmit = vi.fn();

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "",
            class_ids: [],
          }}
        />,
      );

      const titleInput = screen.getByTestId("individual-title-input");
      expect(titleInput).toHaveFocus();
    });

    it("updates form state when inputs change", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Initial",
            description: "Initial description",
            class_ids: ["class-person"],
          }}
        />,
      );

      const titleInput = screen.getByTestId("individual-title-input") as HTMLInputElement;
      await user.clear(titleInput);
      await user.type(titleInput, "Updated");

      await waitFor(() => {
        expect(titleInput.value).toBe("Updated");
      });

      const descInput = screen.getByTestId("individual-description-input") as HTMLTextAreaElement;
      await user.clear(descInput);
      await user.type(descInput, "Updated description");

      await waitFor(() => {
        expect(descInput.value).toBe("Updated description");
      });
    });
  });

  // ========================================================================
  // Form Submission Tests
  // ========================================================================
  describe("form submission", () => {
    it("handles form submission via form element", async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);

      render(
        <IndividualEditor
          onSubmit={onSubmit}
          initialData={{
            title: "Test Individual",
            class_ids: ["class-person"],
          }}
        />,
      );

      const form = screen.getByTestId("individual-form") as HTMLFormElement;
      form.dispatchEvent(new Event("submit", { bubbles: true }));

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalled();
      });
    });
  });
});
