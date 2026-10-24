import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { createGraphView } from "@/api/services/__tests__/fixtures/graph.fixtures";
import { GraphNodeInspector } from "../GraphNodeInspector";

// Use the real Heimdall GraphInspector so relationship links render as shipped
// (vitest.setup.ts mocks the package globally).
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));

const view = createGraphView();

function renderInspector(overrides: Partial<Parameters<typeof GraphNodeInspector>[0]> = {}) {
  const props = {
    view,
    nodeId: "checkout",
    isFocused: false,
    onFocus: vi.fn(),
    onNavigate: vi.fn(),
    emptyStateText: "No node selected",
    ...overrides,
  };
  render(<GraphNodeInspector {...props} />);
  return props;
}

describe("GraphNodeInspector", () => {
  it("renders a labelled region with data-testid", () => {
    renderInspector();
    const root = screen.getByTestId("node-inspector");
    expect(root).toHaveAttribute("role", "region");
    expect(root).toHaveAttribute("aria-label", "Selected node details");
    expect(root).toHaveClass("graph-node-inspector");
  });

  it("shows the empty state and no focus button without a selection", () => {
    renderInspector({ nodeId: undefined });
    expect(screen.getByText("No node selected")).toBeInTheDocument();
    expect(screen.queryByTestId("node-inspector-focus-button")).not.toBeInTheDocument();
  });

  it("shows class, layer, taxonomy and description for an individual", () => {
    renderInspector();
    expect(
      screen.getByText("Checkout", { selector: ".graph-inspector__title" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Checkout service")).toBeInTheDocument();
    expect(screen.getByText("Individual")).toBeInTheDocument();
    // KV grid rows
    expect(screen.getByText("Class")).toBeInTheDocument();
    expect(screen.getAllByText("Business Service").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Business Layer").length).toBeGreaterThan(0);
    expect(screen.getByText("Documentation Robotics")).toBeInTheDocument();
  });

  it("shows the identifier for a class", () => {
    renderInspector({ nodeId: "svc" });
    expect(screen.getByText("business_service")).toBeInTheDocument();
    expect(screen.queryByText("Individual")).not.toBeInTheDocument();
  });

  it("lists every relationship with predicate and endpoint", () => {
    renderInspector();
    expect(screen.getByTestId("node-inspector-relationship-count")).toHaveTextContent(
      "2 relationships",
    );
    expect(screen.getByText("realized by")).toBeInTheDocument();
    expect(screen.getByText("instance of")).toBeInTheDocument();
    const target = screen.getByRole("button", { name: /POST \/orders/ });
    expect(target).toHaveClass("graph-inspector__rel-target");
    // Endpoint colored by its layer (layer-api is index 2)
    expect(target).toHaveAttribute("data-domain", "layer-2");
  });

  it("navigates (re-focuses) when a relationship endpoint is clicked", async () => {
    const user = userEvent.setup();
    const props = renderInspector();
    await user.click(screen.getByRole("button", { name: /POST \/orders/ }));
    expect(props.onNavigate).toHaveBeenCalledWith("post-order");
  });

  it("focuses the selected node from the focus button", async () => {
    const user = userEvent.setup();
    const props = renderInspector();
    const button = screen.getByTestId("node-inspector-focus-button");
    expect(button).toHaveAttribute("aria-pressed", "false");
    expect(button).toHaveTextContent("Focus neighborhood");
    await user.click(button);
    expect(props.onFocus).toHaveBeenCalledWith("checkout");
  });

  it("disables the focus button when the node is already focused", () => {
    renderInspector({ isFocused: true });
    const button = screen.getByTestId("node-inspector-focus-button");
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("aria-pressed", "true");
    expect(button).toHaveTextContent("Focused");
  });
});
