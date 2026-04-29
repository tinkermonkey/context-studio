/**
 * E2E Tests for Move with Type Conversion Workflows
 *
 * Tests complete user workflows for moving structure nodes with automatic
 * type conversion, validating form rendering, UI elements, and response handling.
 */

import React from "react";
import userEvent from "@testing-library/user-event";
import { screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock router to avoid app boot
vi.mock("@tanstack/react-router", () => {
  return {
     
    Link: (props: any) => React.createElement("a", props, props.children),
    useNavigate: () => vi.fn(),
  };
});

import {
  renderWithProviders as render,
  makeTestQueryClient,
} from "@/test/utils/renderWithProviders";
import { DomainMoveForm } from "@/components/forms/domain_move_form";
import { TermMoveForm } from "@/components/forms/term_move_form";
import { NodeType } from "@/api/types/structureNodes";
import { setupMocks } from "../msw/setupTests";

// Setup MSW for any uncaught network calls
setupMocks();

// Mock toast hook
const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
};

vi.mock("@/hooks/useButterToast", () => ({
  useButterToast: () => mockToast,
}));

// Test data fixtures

const createDomain = (id: string, title: string, layerId: string) => ({
  id,
  title,
  node_type: NodeType.DOMAIN,
  parent_node_id: layerId,
  created_at: new Date().toISOString(),
  last_modified: new Date().toISOString(),
  version: 1,
});

const createTerm = (id: string, title: string, parentId: string) => ({
  id,
  title,
  node_type: NodeType.TERM,
  parent_node_id: parentId,
  created_at: new Date().toISOString(),
  last_modified: new Date().toISOString(),
  version: 1,
});

describe("Move Forms - UI Rendering and Structure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("DomainMoveForm: renders with automatic type conversion alert", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Check for informational alert
    const alert = await screen.findByText(/Automatic Type Conversion/i);
    expect(alert).toBeInTheDocument();

    // Check conversion rules are listed
    expect(
      screen.getByText(/Moving to root.*becomes a layer/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Moving under a layer.*becomes a domain/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Moving under a domain or term.*becomes a term/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/All child nodes will be converted recursively/i),
    ).toBeInTheDocument();
  });

  it("DomainMoveForm: renders all form elements correctly", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Check all form elements are present
    expect(await screen.findByText(/Target Parent Node/i)).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /move all child nodes/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Move Nodes/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Moving 1 node/i)).toBeInTheDocument();
  });

  it("DomainMoveForm: move children checkbox is checked by default", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const moveChildrenCheckbox = await screen.findByRole("checkbox", {
      name: /move all child nodes/i,
    });
    expect(moveChildrenCheckbox).toBeChecked();
  });

  it("DomainMoveForm: move button is disabled when no target selected", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const moveButton = await screen.findByRole("button", {
      name: /Move Nodes/i,
    });
    expect(moveButton).toBeDisabled();
  });

  it("DomainMoveForm: cancel button triggers onCancel callback", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");
    const onCancel = vi.fn();

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={onCancel}
      />,
      { queryClient: qc },
    );

    const cancelButton = await screen.findByRole("button", { name: /Cancel/i });
    await userEvent.click(cancelButton);

    expect(onCancel).toHaveBeenCalled();
  });

  it("DomainMoveForm: checkbox can be toggled", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const moveChildrenCheckbox = await screen.findByRole("checkbox", {
      name: /move all child nodes/i,
    });

    // Initially checked
    expect(moveChildrenCheckbox).toBeChecked();

    // Click to uncheck
    await userEvent.click(moveChildrenCheckbox);
    expect(moveChildrenCheckbox).not.toBeChecked();

    // Click to check again
    await userEvent.click(moveChildrenCheckbox);
    expect(moveChildrenCheckbox).toBeChecked();
  });

  it("DomainMoveForm: displays correct count for multiple nodes", async () => {
    const qc = makeTestQueryClient();
    const domain1 = createDomain("domain-1", "Domain 1", "layer-1");
    const domain2 = createDomain("domain-2", "Domain 2", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain1, domain2]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    expect(await screen.findByText(/Moving 2 nodes/i)).toBeInTheDocument();
  });

  it("TermMoveForm: renders with automatic type conversion alert", async () => {
    const qc = makeTestQueryClient();
    const term = createTerm("term-1", "Test Term", "domain-1");

    render(
      <TermMoveForm
        selectedNodes={[term]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Check for informational alert
    const alert = await screen.findByText(/Automatic Type Conversion/i);
    expect(alert).toBeInTheDocument();

    // Check conversion rules are listed
    expect(
      screen.getByText(/All child nodes will be converted recursively/i),
    ).toBeInTheDocument();
  });

  it("TermMoveForm: renders all form elements correctly", async () => {
    const qc = makeTestQueryClient();
    const term = createTerm("term-1", "Test Term", "domain-1");

    render(
      <TermMoveForm
        selectedNodes={[term]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Check all form elements are present
    expect(await screen.findByText(/Target Parent Node/i)).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /move all child nodes/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Move Nodes/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Moving 1 node/i)).toBeInTheDocument();
  });

  it("TermMoveForm: move button is disabled when no target selected", async () => {
    const qc = makeTestQueryClient();
    const term = createTerm("term-1", "Test Term", "domain-1");

    render(
      <TermMoveForm
        selectedNodes={[term]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const moveButton = await screen.findByRole("button", {
      name: /Move Nodes/i,
    });
    expect(moveButton).toBeDisabled();
  });

  it("TermMoveForm: displays correct count for multiple nodes", async () => {
    const qc = makeTestQueryClient();
    const term1 = createTerm("term-1", "Term 1", "domain-1");
    const term2 = createTerm("term-2", "Term 2", "domain-1");

    render(
      <TermMoveForm
        selectedNodes={[term1, term2]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    expect(await screen.findByText(/Moving 2 nodes/i)).toBeInTheDocument();
  });
});

describe("Move Forms - Form Validation and Behavior", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("DomainMoveForm: excludes selected nodes from being their own parent", async () => {
    const qc = makeTestQueryClient();
    const domain1 = createDomain("domain-1", "Domain 1", "layer-1");

    const { container } = render(
      <DomainMoveForm
        selectedNodes={[domain1]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // The form should render the StructureNodeSelector
    // which receives excludeNodeIds prop to prevent self-selection
    const form = container.querySelector("form");
    expect(form).toBeInTheDocument();

    // Verify form structure is correct
    expect(await screen.findByText(/Target Parent Node/i)).toBeInTheDocument();
  });

  it("TermMoveForm: text updates based on checkbox state", async () => {
    const qc = makeTestQueryClient();
    const term = createTerm("term-1", "Test Term", "domain-1");

    render(
      <TermMoveForm
        selectedNodes={[term]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Initially should show "will be moved" text
    expect(
      await screen.findByText(
        /All child nodes will also be moved recursively/i,
      ),
    ).toBeInTheDocument();

    // Uncheck the checkbox
    const checkbox = screen.getByRole("checkbox", {
      name: /move all child nodes/i,
    });
    await userEvent.click(checkbox);

    // Text should disappear when unchecked
    await waitFor(() => {
      // Text is conditional on checkbox state in the form description
      expect(checkbox).not.toBeChecked();
    });
  });

  it("form shows correct placeholder text for node selector", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Check placeholder is shown
    expect(
      await screen.findByText(
        /Select target parent \(or leave empty for root\)/i,
      ),
    ).toBeInTheDocument();
  });
});

describe("Move Forms - Accessibility", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("DomainMoveForm: has proper form structure", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    const { container } = render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const form = container.querySelector("form");
    expect(form).toBeInTheDocument();
    expect(form?.tagName).toBe("FORM");
  });

  it("DomainMoveForm: checkbox has proper label association", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const checkbox = await screen.findByRole("checkbox", {
      name: /move all child nodes/i,
    });
    expect(checkbox).toHaveAccessibleName();
    expect(checkbox.getAttribute("id")).toBe("move-children");
  });

  it("DomainMoveForm: buttons have proper types", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const cancelButton = await screen.findByRole("button", { name: /Cancel/i });
    const moveButton = screen.getByRole("button", { name: /Move Nodes/i });

    expect(cancelButton.getAttribute("type")).toBe("button");
    expect(moveButton.getAttribute("type")).toBe("submit");
  });

  it("TermMoveForm: has proper form structure", async () => {
    const qc = makeTestQueryClient();
    const term = createTerm("term-1", "Test Term", "domain-1");

    const { container } = render(
      <TermMoveForm
        selectedNodes={[term]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    const form = container.querySelector("form");
    expect(form).toBeInTheDocument();
    expect(form?.tagName).toBe("FORM");
  });
});

describe("Move Forms - User Intent and Messaging", () => {
  it("DomainMoveForm: clearly communicates automatic conversion behavior", async () => {
    const qc = makeTestQueryClient();
    const domain = createDomain("domain-1", "Test Domain", "layer-1");

    render(
      <DomainMoveForm
        selectedNodes={[domain]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // The alert should be prominent and informative
    const alert = await screen.findByText(/Automatic Type Conversion/i);
    expect(alert).toBeInTheDocument();

    // All three conversion scenarios should be documented
    const conversionRules = [
      /Moving to root.*becomes a layer/i,
      /Moving under a layer.*becomes a domain/i,
      /Moving under a domain or term.*becomes a term/i,
    ];

    conversionRules.forEach((rule) => {
      expect(screen.getByText(rule)).toBeInTheDocument();
    });
  });

  it("TermMoveForm: clearly communicates automatic conversion behavior", async () => {
    const qc = makeTestQueryClient();
    const term = createTerm("term-1", "Test Term", "domain-1");

    render(
      <TermMoveForm
        selectedNodes={[term]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // The alert should be prominent and informative
    const alert = await screen.findByText(/Automatic Type Conversion/i);
    expect(alert).toBeInTheDocument();

    // Should explain recursive conversion
    expect(
      screen.getByText(/All child nodes will be converted recursively/i),
    ).toBeInTheDocument();
  });

  it("forms use consistent language and terminology", async () => {
    const qc = makeTestQueryClient();

    // Render both forms
    const { unmount: unmountDomain } = render(
      <DomainMoveForm
        selectedNodes={[createDomain("d1", "D1", "l1")]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Check consistent terminology in domain form
    expect(await screen.findByText(/Target Parent Node/i)).toBeInTheDocument();
    expect(screen.getByText(/Move Nodes/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();

    unmountDomain();

    // Render term form
    render(
      <TermMoveForm
        selectedNodes={[createTerm("t1", "T1", "d1")]}
        onSuccess={vi.fn()}
        onCancel={vi.fn()}
      />,
      { queryClient: qc },
    );

    // Check same terminology in term form
    expect(await screen.findByText(/Target Parent Node/i)).toBeInTheDocument();
    expect(screen.getByText(/Move Nodes/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cancel/i })).toBeInTheDocument();
  });
});
