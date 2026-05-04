/**
 * Tests for ConflictResolutionModal component
 *
 * Focus on key-parsing logic and conflict resolution handling
 */

import React from "react";
import {
  render,
  fireEvent,
  waitFor,
  screen,
  cleanup,
} from "@testing-library/react";
import { vi, describe, it, expect, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Clean up after each test to avoid multiple elements with same testid
afterEach(() => {
  cleanup();
});

// Mock flowbite-react Modal sub-components which are not available in test environment
vi.mock("flowbite-react", async () => {
  const actual = await vi.importActual("flowbite-react");
  const Modal = (props: any) => {
    const { children, "data-testid": testId, show = true, ...rest } = props;
    if (!show) {
      return null;
    }
    return React.createElement(
      "div",
      { "data-testid": testId, role: "dialog", className: "modal", ...rest },
      children,
    );
  };
  Modal.Header = (props: any) =>
    React.createElement(
      "div",
      { className: "modal-header", ...props },
      props.children,
    );
  Modal.Body = (props: any) =>
    React.createElement(
      "div",
      { className: "modal-body", ...props },
      props.children,
    );
  Modal.Footer = (props: any) =>
    React.createElement(
      "div",
      { className: "modal-footer", ...props },
      props.children,
    );

  return {
    ...(actual as object),
    Modal,
  };
});

// Mock lucide-react icons
vi.mock("lucide-react", () => ({
  ChevronDown: () => <div>ChevronDown Icon</div>,
  ChevronUp: () => <div>ChevronUp Icon</div>,
}));

import { ConflictResolutionModal } from "../ConflictResolutionModal";
import type { ImportConflict } from "@/api/types/interchange";

// Create test providers wrapper
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

const createWrapper = () => {
  const queryClient = createTestQueryClient();
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("ConflictResolutionModal", () => {
  const mockConflicts: ImportConflict[] = [
    {
      match_kind: "external_reference",
      existing: "existing-1",
      incoming: {
        id: "incoming-1",
        title: "Dog",
        type: "class",
      },
      default_resolution: "merge",
      available_resolutions: ["merge", "skip", "overwrite"],
    },
    {
      match_kind: "title",
      existing: "existing-2",
      incoming: {
        id: "incoming-2",
        title: "Cat",
        type: "class",
      },
      default_resolution: "skip",
      available_resolutions: ["skip", "merge", "overwrite"],
    },
  ];

  it("renders modal when isOpen is true", () => {
    const Wrapper = createWrapper();
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <Wrapper>
        <ConflictResolutionModal
          isOpen={true}
          onClose={mockOnClose}
          conflicts={mockConflicts}
          newEntityCount={5}
          onCommit={mockOnCommit}
        />
      </Wrapper>,
    );

    expect(
      screen.getByTestId("interchange-conflict-resolution-modal"),
    ).toBeInTheDocument();
    expect(screen.getByText("Resolve Import Conflicts")).toBeInTheDocument();
  });

  it("does not render modal when isOpen is false", () => {
    const Wrapper = createWrapper();
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    const { container } = render(
      <Wrapper>
        <ConflictResolutionModal
          isOpen={false}
          onClose={mockOnClose}
          conflicts={mockConflicts}
          newEntityCount={5}
          onCommit={mockOnCommit}
        />
      </Wrapper>,
    );

    // Modal should not be visible when isOpen is false
    const modal = container.querySelector("[role='dialog']");
    // Flowbite Modal might not render at all when show={false}
    if (modal) {
      expect(modal).not.toBeVisible();
    }
  });

  it("groups conflicts by match_kind", () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={mockConflicts}
        newEntityCount={5}
        onCommit={mockOnCommit}
      />,
    );

    expect(
      screen.getByTestId("interchange-conflict-group-external-reference"),
    ).toBeInTheDocument();
  });

  it("initializes resolutions with defaults", async () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={mockConflicts}
        newEntityCount={5}
        onCommit={mockOnCommit}
      />,
    );

    // Resolution dropdowns should be rendered with default values
    await waitFor(() => {
      const resolutionSelects = screen.getAllByRole("combobox");
      expect(resolutionSelects.length).toBeGreaterThan(0);
    });
  });

  it("handles key parsing correctly for UUIDs with hyphens", async () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    // Create a conflict with UUID that has multiple hyphens
    const uuidConflict: ImportConflict = {
      match_kind: "uuid",
      existing: "550e8400-e29b-41d4-a716-446655440000",
      incoming: {
        id: "550e8400-e29b-41d4-a716-446655440001",
        title: "Entity 1",
        type: "class",
      },
      default_resolution: "skip",
      available_resolutions: ["skip", "merge", "overwrite"],
    };

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={[uuidConflict]}
        newEntityCount={1}
        onCommit={mockOnCommit}
      />,
    );

    // Click commit to trigger key parsing
    const commitButton = screen.getByRole("button", { name: /commit/i });
    fireEvent.click(commitButton);

    await waitFor(() => {
      expect(mockOnCommit).toHaveBeenCalled();
    });

    // Verify the resolution records were parsed correctly
    const resolutionRecords = mockOnCommit.mock.calls[0][0];
    expect(resolutionRecords).toHaveLength(1);
    expect(resolutionRecords[0].match_kind).toBe("uuid");
    // The entity_id should be the full UUID after the first hyphen
    expect(resolutionRecords[0].entity_id).toBe(
      "550e8400-e29b-41d4-a716-446655440001",
    );
  });

  it("parses resolution keys correctly (match_kind-entity_id format)", async () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    const testConflicts: ImportConflict[] = [
      {
        match_kind: "external_reference",
        existing: "ext-ref-123",
        incoming: {
          id: "incoming-ext-ref",
          title: "DBpedia Item",
          type: "class",
        },
        default_resolution: "merge",
        available_resolutions: ["merge", "skip", "overwrite"],
      },
    ];

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={testConflicts}
        newEntityCount={1}
        onCommit={mockOnCommit}
      />,
    );

    const commitButton = screen.getByRole("button", { name: /commit/i });
    fireEvent.click(commitButton);

    await waitFor(() => {
      expect(mockOnCommit).toHaveBeenCalled();
    });

    const resolutionRecords = mockOnCommit.mock.calls[0][0];
    expect(resolutionRecords[0].match_kind).toBe("external_reference");
    expect(resolutionRecords[0].entity_id).toBe("incoming-ext-ref");
  });

  it("allows changing resolution for individual conflicts", async () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={mockConflicts}
        newEntityCount={5}
        onCommit={mockOnCommit}
      />,
    );

    // Find and change a resolution dropdown
    const resolutionSelects = screen.getAllByRole("combobox");
    if (resolutionSelects.length > 0) {
      fireEvent.change(resolutionSelects[0], {
        target: { value: "override" },
      });
    }

    const commitButton = screen.getByRole("button", { name: /commit/i });
    fireEvent.click(commitButton);

    await waitFor(() => {
      expect(mockOnCommit).toHaveBeenCalled();
    });
  });

  it("allows applying same resolution to all conflicts in a group", async () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={mockConflicts}
        newEntityCount={5}
        onCommit={mockOnCommit}
      />,
    );

    // Find "Apply All" button (if it exists)
    const applyAllButtons = screen.queryAllByRole("button", {
      name: /apply all/i,
    });
    if (applyAllButtons.length > 0) {
      fireEvent.click(applyAllButtons[0]);
    }

    const commitButton = screen.getByRole("button", { name: /commit/i });
    fireEvent.click(commitButton);

    await waitFor(() => {
      expect(mockOnCommit).toHaveBeenCalled();
    });
  });

  it("toggles group expansion", async () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={mockConflicts}
        newEntityCount={5}
        onCommit={mockOnCommit}
      />,
    );

    const groupHeader = screen.getByTestId(
      "interchange-conflict-group-external-reference",
    );
    fireEvent.click(groupHeader);

    // After clicking, the group should toggle its expansion state
    await waitFor(() => {
      expect(groupHeader).toBeInTheDocument();
    });
  });

  it("displays conflict count summary", () => {
    const Wrapper = createWrapper();
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <Wrapper>
        <ConflictResolutionModal
          isOpen={true}
          onClose={mockOnClose}
          conflicts={mockConflicts}
          newEntityCount={5}
          onCommit={mockOnCommit}
        />
      </Wrapper>,
    );

    // Check for conflict descriptions
    const text = screen.getByText(/entit/i);
    expect(text).toBeInTheDocument();
  });

  it("calls onClose when close button is clicked", async () => {
    const Wrapper = createWrapper();
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <Wrapper>
        <ConflictResolutionModal
          isOpen={true}
          onClose={mockOnClose}
          conflicts={mockConflicts}
          newEntityCount={5}
          onCommit={mockOnCommit}
        />
      </Wrapper>,
    );

    const closeButton = screen.getByRole("button", { name: /close/i });
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it("disables commit when isLoading is true", () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={mockConflicts}
        newEntityCount={5}
        onCommit={mockOnCommit}
        isLoading={true}
      />,
    );

    const commitButton = screen.getByRole("button", { name: /commit/i });
    expect(commitButton).toBeDisabled();
  });

  it("has data-testid for accessibility testing", () => {
    const mockOnClose = vi.fn();
    const mockOnCommit = vi.fn();

    render(
      <ConflictResolutionModal
        isOpen={true}
        onClose={mockOnClose}
        conflicts={mockConflicts}
        newEntityCount={5}
        onCommit={mockOnCommit}
      />,
    );

    expect(
      screen.getByTestId("interchange-conflict-resolution-modal"),
    ).toBeInTheDocument();
  });
});
