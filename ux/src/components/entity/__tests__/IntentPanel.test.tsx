import { describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { IntentPanel } from "../IntentPanel";

function renderPanel(props: Partial<Parameters<typeof IntentPanel>[0]> = {}) {
  const onSave = vi.fn().mockResolvedValue({});
  render(
    <IntentPanel
      title="Summary"
      note="What it is for."
      value="A household knowledge graph."
      emptyText="No summary yet."
      onSave={onSave}
      data-testid="taxonomy-summary"
      {...props}
    />,
  );
  return { onSave };
}

describe("IntentPanel", () => {
  it("shows plain text with the definition style and a note", () => {
    renderPanel();

    expect(screen.getByTestId("taxonomy-summary")).toBeInTheDocument();
    expect(screen.getByTestId("taxonomy-summary-text")).toHaveClass("entity-definition");
    expect(screen.getByText("What it is for.")).toHaveClass("entity-note");
    expect(screen.getByTestId("taxonomy-summary-edit")).toHaveTextContent("Edit summary");
  });

  it("renders markdown when asked", () => {
    renderPanel({ title: "Vision", markdown: true, value: "## Purpose\n\n- one\n- two" });

    const text = screen.getByTestId("taxonomy-summary-text");
    expect(text).toHaveClass("intent-markdown");
    expect(screen.getByRole("heading", { name: "Purpose" })).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("opens absolute links in a new tab and shows relative links as text", () => {
    renderPanel({
      title: "Vision",
      markdown: true,
      value: "See [the spec](docs/ONTOLOGY.md) and [the site](https://example.com).",
    });

    expect(screen.queryByRole("link", { name: "the spec" })).not.toBeInTheDocument();
    expect(screen.getByText("the spec")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "the site" })).toHaveAttribute("target", "_blank");
  });

  it("shows the empty text when there is no value", () => {
    renderPanel({ value: null });

    expect(screen.getByTestId("taxonomy-summary-empty")).toHaveTextContent("No summary yet.");
    expect(screen.queryByTestId("taxonomy-summary-text")).not.toBeInTheDocument();
  });

  it("saves the trimmed draft and leaves edit mode", async () => {
    const user = userEvent.setup();
    const { onSave } = renderPanel();

    await user.click(screen.getByTestId("taxonomy-summary-edit"));
    const input = screen.getByRole("textbox", { name: "Summary" });
    await user.clear(input);
    await user.type(input, "  Revised summary.  ");
    await user.click(screen.getByTestId("taxonomy-summary-save"));

    expect(onSave).toHaveBeenCalledWith("Revised summary.");
    expect(screen.queryByTestId("taxonomy-summary-input")).not.toBeInTheDocument();
  });

  it("cancel discards the draft", async () => {
    const user = userEvent.setup();
    const { onSave } = renderPanel();

    await user.click(screen.getByTestId("taxonomy-summary-edit"));
    await user.type(screen.getByTestId("taxonomy-summary-input"), " extra");
    await user.click(screen.getByTestId("taxonomy-summary-cancel"));

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByTestId("taxonomy-summary-text")).toHaveTextContent(
      "A household knowledge graph.",
    );
  });

  it("keeps the editor open when saving fails", async () => {
    const user = userEvent.setup();
    renderPanel({ onSave: vi.fn().mockRejectedValue(new Error("boom")) });

    await user.click(screen.getByTestId("taxonomy-summary-edit"));
    await user.click(screen.getByTestId("taxonomy-summary-save"));

    expect(await screen.findByTestId("taxonomy-summary-input")).toBeInTheDocument();
  });
});
