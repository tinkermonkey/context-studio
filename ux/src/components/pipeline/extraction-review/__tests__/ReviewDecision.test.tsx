import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ReviewDecision } from "../ReviewDecision";

describe("ReviewDecision", () => {
  it("renders a labelled group with a data-testid and two toggle buttons", () => {
    render(
      <ReviewDecision
        value="pending"
        onChange={vi.fn()}
        data-testid="extraction-review-schema-decision-sc-0"
      />,
    );
    const group = screen.getByTestId("extraction-review-schema-decision-sc-0");
    expect(group).toHaveAttribute("role", "group");
    expect(group).toHaveAttribute("aria-label", "Review decision");
    expect(group).toHaveClass("xr-decision");
    expect(screen.getByRole("button", { name: "Accept" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Reject" })).toHaveAttribute("aria-pressed", "false");
  });

  it.each([
    ["pending", "btn--ghost", "btn--ghost"],
    ["yes", "btn--primary", "btn--ghost"],
    ["no", "btn--ghost", "btn--danger"],
  ] as const)("uses the right button variants when %s", (value, yesClass, noClass) => {
    render(
      <ReviewDecision
        value={value}
        onChange={vi.fn()}
        data-testid="extraction-review-schema-decision-sc-0"
      />,
    );
    expect(screen.getByTestId("extraction-review-schema-decision-sc-0-yes")).toHaveClass(yesClass);
    expect(screen.getByTestId("extraction-review-schema-decision-sc-0-no")).toHaveClass(noClass);
    expect(screen.getByTestId("extraction-review-schema-decision-sc-0-yes")).toHaveAttribute(
      "aria-pressed",
      String(value === "yes"),
    );
    expect(screen.getByTestId("extraction-review-schema-decision-sc-0-no")).toHaveAttribute(
      "aria-pressed",
      String(value === "no"),
    );
  });

  it("sets a choice and toggles the active choice back to pending", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<ReviewDecision value="pending" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onChange).toHaveBeenLastCalledWith("no");

    rerender(<ReviewDecision value="no" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onChange).toHaveBeenLastCalledWith("pending");
  });

  it("supports merge / keep-separate labels and compact icon-only buttons", () => {
    render(
      <ReviewDecision value="yes" onChange={vi.fn()} yes="Merge" no="Keep separate" compact />,
    );
    const merge = screen.getByRole("button", { name: "Merge" });
    expect(merge).toHaveAttribute("aria-pressed", "true");
    expect(merge).not.toHaveTextContent("Merge");
    expect(screen.getByRole("button", { name: "Keep separate" })).toBeInTheDocument();
  });

  it("does not propagate clicks to a clickable row", async () => {
    const onRow = vi.fn();
    render(
      <div onClick={onRow}>
        <ReviewDecision value="pending" onChange={vi.fn()} />
      </div>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    expect(onRow).not.toHaveBeenCalled();
  });

  it("disables only the no choice when a reason is given, and shows the reason", async () => {
    const onChange = vi.fn();
    render(
      <ReviewDecision
        value="pending"
        onChange={onChange}
        yes="Merge"
        no="Keep separate"
        noDisabledReason="Same title in the same class"
      />,
    );
    const no = screen.getByRole("button", { name: "Keep separate" });
    expect(no).toBeDisabled();
    expect(no).toHaveAttribute("aria-disabled", "true");
    expect(no).toHaveAttribute("title", "Same title in the same class");
    await userEvent.click(no);
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Merge" })).toBeEnabled();
  });
});
