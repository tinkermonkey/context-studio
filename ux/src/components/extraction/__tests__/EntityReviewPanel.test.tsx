import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/api/utils/queryClient";
import { EntityReviewPanel } from "../EntityReviewPanel";
import * as ontologyHooks from "@/api/hooks/ontology";
import { describe, it, expect, beforeEach, vi } from "vitest";
import type { components } from "@/api/types";

type ExtractedEntitySchema = components["schemas"]["ExtractedEntitySchema"];

const mockToast = vi.fn();
vi.mock("@/components/ui/Toast", () => ({
  useToasts: () => ({
    toast: mockToast,
  }),
}));

vi.mock("@/api/hooks/ontology");

const mockCreateClass = vi.fn();
const mockUseCreateClass = vi.mocked(ontologyHooks.useCreateClass);
const mockUseClasses = vi.mocked(ontologyHooks.useClasses);
const mockUseSchemes = vi.mocked(ontologyHooks.useSchemes);

const mockEntity: ExtractedEntitySchema = {
  id: "entity-1",
  label: "Test Entity",
  entity_type: "Person",
  confidence: 0.95,
  description: "A test entity",
  source_layer: 0,
  matched_class_id: null,
};

const mockEntity2: ExtractedEntitySchema = {
  id: "entity-2",
  label: "Another Entity",
  entity_type: "Organization",
  confidence: 0.87,
  description: null,
  source_layer: 0,
  matched_class_id: null,
};

const mockClass1 = { id: "class-1", title: "Person Class" };
const mockClass2 = { id: "class-2", title: "Organization Class" };
const mockScheme = { id: "scheme-1", title: "Main Scheme" };

function renderWithProvider(component: React.ReactElement) {
  return render(<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>);
}

describe("EntityReviewPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockToast.mockClear();

    mockUseCreateClass.mockReturnValue({
      mutateAsync: mockCreateClass,
      isPending: false,
      status: "idle",
    } as any);

    mockUseClasses.mockReturnValue({
      data: { items: [mockClass1, mockClass2] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      status: "success",
    } as any);

    mockUseSchemes.mockReturnValue({
      data: { items: [mockScheme] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      status: "success",
    } as any);
  });

  describe("visibility", () => {
    it("hides when entities array is empty", () => {
      const { container } = renderWithProvider(<EntityReviewPanel entities={[]} layerIndex={0} />);
      expect(
        container.querySelector('[data-testid="entity-review-panel-0"]'),
      ).not.toBeInTheDocument();
    });

    it("shows loading skeletons while isLoading is true", () => {
      const { container } = renderWithProvider(
        <EntityReviewPanel entities={[mockEntity]} layerIndex={0} isLoading={true} />,
      );
      // Skeletons are divs with specific animation styles
      const skeletonElements = container.querySelectorAll(
        'div[style*="animation: skeleton-shimmer"]',
      );
      expect(skeletonElements.length).toBeGreaterThan(0);
    });

    it("shows 'all reviewed' empty state when no unlinked entities", () => {
      const linkedEntity: ExtractedEntitySchema = {
        ...mockEntity,
        matched_class_id: "class-1",
      };
      const { container } = renderWithProvider(
        <EntityReviewPanel entities={[linkedEntity]} layerIndex={0} />,
      );
      expect(container.textContent?.includes("reviewed")).toBeTruthy();
    });

    it("renders populated state with unlinked entities", () => {
      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);
      expect(screen.getByText("Test Entity")).toBeInTheDocument();
      expect(screen.getByText("Another Entity")).toBeInTheDocument();
    });
  });

  describe("entity filtering", () => {
    it("filters out entities with matched_class_id", () => {
      const linkedEntity: ExtractedEntitySchema = {
        ...mockEntity,
        matched_class_id: "class-1",
      };
      renderWithProvider(
        <EntityReviewPanel entities={[linkedEntity, mockEntity2]} layerIndex={0} />,
      );
      expect(screen.queryByText("Test Entity")).not.toBeInTheDocument();
      expect(screen.getByText("Another Entity")).toBeInTheDocument();
    });

    it("filters out rejected entities", async () => {
      const user = userEvent.setup();
      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      const rejectButton = screen.getByTestId(`entity-review-reject-${mockEntity.id}`);
      await user.click(rejectButton);

      expect(screen.queryByText("Test Entity")).not.toBeInTheDocument();
      expect(screen.getByText("Another Entity")).toBeInTheDocument();
    });

    it("filters out linked entities", async () => {
      const user = userEvent.setup();
      mockCreateClass.mockResolvedValueOnce({});

      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      const approveButton = screen.getByTestId(`entity-review-approve-${mockEntity.id}`);
      await user.click(approveButton);

      expect(screen.queryByText("Test Entity")).not.toBeInTheDocument();
      expect(screen.getByText("Another Entity")).toBeInTheDocument();
    });
  });

  describe("confidence rendering", () => {
    it("renders confidence percentage correctly", () => {
      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);
      expect(screen.getByText("95%")).toBeInTheDocument();
    });

    it("renders em-dash for null confidence", () => {
      const noConfidenceEntity: ExtractedEntitySchema = {
        ...mockEntity,
        confidence: null as any,
      };
      renderWithProvider(<EntityReviewPanel entities={[noConfidenceEntity]} layerIndex={0} />);
      expect(screen.getByText("—")).toBeInTheDocument();
    });

    it("renders em-dash for undefined confidence", () => {
      const noConfidenceEntity: ExtractedEntitySchema = {
        ...mockEntity,
        confidence: undefined as any,
      };
      renderWithProvider(<EntityReviewPanel entities={[noConfidenceEntity]} layerIndex={0} />);
      expect(screen.getByText("—")).toBeInTheDocument();
    });
  });

  describe("individual entity row", () => {
    it("renders entity label and entity_type chip", () => {
      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);
      expect(screen.getByText("Test Entity")).toBeInTheDocument();
      expect(screen.getByText("Person")).toBeInTheDocument();
    });

    it("displays approve and reject buttons", () => {
      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);
      expect(screen.getByTestId(`entity-review-approve-${mockEntity.id}`)).toBeInTheDocument();
      expect(screen.getByTestId(`entity-review-reject-${mockEntity.id}`)).toBeInTheDocument();
    });

    it("disables buttons when isProcessing is true", async () => {
      mockCreateClass.mockImplementationOnce(() => new Promise(() => {})); // Never resolves
      const user = userEvent.setup();

      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      const approveButton = screen.getByTestId(`entity-review-approve-${mockEntity.id}`);
      await user.click(approveButton);

      // Other buttons should now be disabled
      const rejectButton2 = screen.getByTestId(`entity-review-reject-${mockEntity2.id}`);
      expect(rejectButton2).toBeDisabled();
    });
  });

  describe("approve single entity", () => {
    it("creates a class under default scheme", async () => {
      const user = userEvent.setup();
      mockCreateClass.mockResolvedValueOnce({
        id: "new-class-1",
        title: "Test Entity",
      });

      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      const approveButton = screen.getByTestId(`entity-review-approve-${mockEntity.id}`);
      await user.click(approveButton);

      expect(mockCreateClass).toHaveBeenCalledWith({
        schemeId: mockScheme.id,
        data: {
          title: mockEntity.label,
          description: mockEntity.description,
        },
      });
    });

    it("adds entity to linkedIds after successful approval", async () => {
      const user = userEvent.setup();
      mockCreateClass.mockResolvedValueOnce({
        id: "new-class-1",
        title: "Test Entity",
      });

      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      const approveButton = screen.getByTestId(`entity-review-approve-${mockEntity.id}`);
      await user.click(approveButton);

      // Entity should disappear from the list
      expect(screen.queryByText("Test Entity")).not.toBeInTheDocument();
      // Other entity should still be there
      expect(screen.getByText("Another Entity")).toBeInTheDocument();
    });

    it("shows success toast after class creation", async () => {
      const user = userEvent.setup();
      mockCreateClass.mockResolvedValueOnce({
        id: "new-class-1",
        title: "Test Entity",
      });

      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      const approveButton = screen.getByTestId(`entity-review-approve-${mockEntity.id}`);
      await user.click(approveButton);

      expect(mockToast).toHaveBeenCalledWith("success", expect.stringContaining("Test Entity"));
    });

    it("shows error toast if no scheme available", async () => {
      const user = userEvent.setup();
      mockUseSchemes.mockReturnValueOnce({
        data: { items: [] },
        isLoading: false,
        error: null,
        status: "success",
      } as any);

      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      const approveButton = screen.getByTestId(`entity-review-approve-${mockEntity.id}`);
      await user.click(approveButton);

      expect(mockToast).toHaveBeenCalledWith(
        "error",
        "No concept scheme available for creating classes",
      );
    });

    it("shows error toast if class creation fails", async () => {
      const user = userEvent.setup();
      const testError = new Error("Creation failed");
      mockCreateClass.mockRejectedValueOnce(testError);

      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      const approveButton = screen.getByTestId(`entity-review-approve-${mockEntity.id}`);
      await user.click(approveButton);

      expect(mockToast).toHaveBeenCalledWith("error", expect.stringContaining("failed"));
    });
  });

  describe("reject entity", () => {
    it("adds entity to rejectedIds", async () => {
      const user = userEvent.setup();
      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      const rejectButton = screen.getByTestId(`entity-review-reject-${mockEntity.id}`);
      await user.click(rejectButton);

      expect(screen.queryByText("Test Entity")).not.toBeInTheDocument();
    });

    it("shows info toast when entity is rejected", async () => {
      const user = userEvent.setup();
      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      const rejectButton = screen.getByTestId(`entity-review-reject-${mockEntity.id}`);
      await user.click(rejectButton);

      expect(mockToast).toHaveBeenCalledWith("info", expect.anything());
    });

    it("entity disappears from unlinked list after rejection", async () => {
      const user = userEvent.setup();
      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      expect(screen.getByText("Test Entity")).toBeInTheDocument();

      const rejectButton = screen.getByTestId(`entity-review-reject-${mockEntity.id}`);
      await user.click(rejectButton);

      expect(screen.queryByText("Test Entity")).not.toBeInTheDocument();
      expect(screen.getByText("Another Entity")).toBeInTheDocument();
    });
  });

  describe("error handling", () => {
    it("shows error banner when classes query fails", () => {
      const testError = new Error("Failed to load classes");
      mockUseClasses.mockReturnValueOnce({
        data: null,
        isLoading: false,
        error: testError,
        refetch: vi.fn(),
        status: "error",
      } as any);

      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      expect(screen.getByText(/Failed to load classes/i)).toBeInTheDocument();
    });

    it("shows error banner when schemes query fails", () => {
      const testError = new Error("Failed to load schemes");
      mockUseSchemes.mockReturnValueOnce({
        data: null,
        isLoading: false,
        error: testError,
        refetch: vi.fn(),
        status: "error",
      } as any);

      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      expect(screen.getByText(/Failed to load concept schemes/i)).toBeInTheDocument();
    });

    it("shows retry button in error banner", () => {
      const testError = new Error("Failed to load classes");
      mockUseClasses.mockReturnValueOnce({
        data: null,
        isLoading: false,
        error: testError,
        refetch: vi.fn(),
        status: "error",
      } as any);

      renderWithProvider(<EntityReviewPanel entities={[mockEntity]} layerIndex={0} />);

      const retryButton = screen.getByRole("button", { name: /retry/i });
      expect(retryButton).toBeInTheDocument();
    });
  });

  describe("batch operations", () => {
    it("approve all creates class for each unlinked entity", async () => {
      const user = userEvent.setup();
      mockCreateClass
        .mockResolvedValueOnce({ id: "new-class-1", title: mockEntity.label })
        .mockResolvedValueOnce({ id: "new-class-2", title: mockEntity2.label });

      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      const approveAllButton = screen.getByRole("button", { name: /approve all/i });
      await user.click(approveAllButton);

      expect(mockCreateClass).toHaveBeenCalledTimes(2);
    });

    it("approve all with partial failure shows success and error messages", async () => {
      const user = userEvent.setup();
      mockCreateClass
        .mockResolvedValueOnce({ id: "new-class-1", title: mockEntity.label })
        .mockRejectedValueOnce(new Error("Creation failed"));

      renderWithProvider(<EntityReviewPanel entities={[mockEntity, mockEntity2]} layerIndex={0} />);

      const approveAllButton = screen.getByRole("button", { name: /approve all/i });
      await user.click(approveAllButton);

      // Should have both success and error toasts
      const calls = mockToast.mock.calls;
      const hasSuccess = calls.some((call) => call[0] === "success");
      const hasError = calls.some((call) => call[0] === "error");

      expect(hasSuccess).toBe(true);
      expect(hasError).toBe(true);
    });
  });
});
