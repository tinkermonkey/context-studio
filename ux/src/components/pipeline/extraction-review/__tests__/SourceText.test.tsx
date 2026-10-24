import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SourceText } from "../SourceText";

const TEXT = "Alpha beta gamma delta";
// "beta gamma" (a) overlaps "gamma delta" (b); "zeta" (c) is unlocated.
const SPANS = [
  { key: "a", quote: "beta gamma", start: 6, end: 16 },
  { key: "b", quote: "gamma delta", start: 11, end: 22 },
  { key: "c", quote: "zeta", start: null, end: null },
];

describe("SourceText", () => {
  it("renders the full text with a data-testid root", () => {
    const { container } = render(
      <SourceText
        text={TEXT}
        spans={SPANS}
        onSelectKey={vi.fn()}
        data-testid="extraction-review-schema-source"
      />,
    );
    expect(screen.getByTestId("extraction-review-schema-source")).toHaveClass("xr-source-text");
    expect(container.textContent).toBe(TEXT);
  });

  it("highlights located spans as buttons and splits overlaps", () => {
    render(<SourceText text={TEXT} spans={SPANS} onSelectKey={vi.fn()} />);
    const marks = screen.getAllByTestId("extraction-review-span");
    expect(marks.map((m) => m.textContent)).toEqual(["beta ", "gamma", " delta"]);
    marks.forEach((m) => {
      expect(m).toHaveAttribute("role", "button");
      expect(m).toHaveAttribute("tabindex", "0");
      expect(m).toHaveClass("xr-span");
    });
    expect(marks[1]).toHaveClass("xr-span--overlap");
    expect(marks[1]).toHaveAttribute("data-span-keys", "a b");
    expect(marks[0]).not.toHaveClass("xr-span--overlap");
  });

  it("does not render unlocated spans", () => {
    render(<SourceText text={TEXT} spans={SPANS} onSelectKey={vi.fn()} />);
    const keys = screen
      .getAllByTestId("extraction-review-span")
      .map((m) => m.getAttribute("data-span-keys"));
    expect(keys.join(" ")).not.toContain("c");
  });

  it("marks segments of the active item with the active class and aria-current", () => {
    render(<SourceText text={TEXT} spans={SPANS} activeKey="b" onSelectKey={vi.fn()} />);
    const [beta, gamma, delta] = screen.getAllByTestId("extraction-review-span");
    expect(beta).not.toHaveClass("xr-span--active");
    expect(gamma).toHaveClass("xr-span--active");
    expect(delta).toHaveClass("xr-span--active");
    expect(delta).toHaveAttribute("aria-current", "true");
    expect(beta).not.toHaveAttribute("aria-current");
  });

  it("selects the linked item on click and cycles through overlapping items", async () => {
    const onSelect = vi.fn();
    const { rerender } = render(<SourceText text={TEXT} spans={SPANS} onSelectKey={onSelect} />);
    await userEvent.click(screen.getAllByTestId("extraction-review-span")[1]);
    expect(onSelect).toHaveBeenLastCalledWith("a");

    rerender(<SourceText text={TEXT} spans={SPANS} activeKey="a" onSelectKey={onSelect} />);
    await userEvent.click(screen.getAllByTestId("extraction-review-span")[1]);
    expect(onSelect).toHaveBeenLastCalledWith("b");
  });

  it("selects with the keyboard (Enter)", async () => {
    const onSelect = vi.fn();
    render(<SourceText text={TEXT} spans={SPANS} onSelectKey={onSelect} />);
    screen.getAllByTestId("extraction-review-span")[2].focus();
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith("b");
  });
});
