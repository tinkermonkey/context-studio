/**
 * The add form's outside press: a press outside it closes it, but not one in a
 * list its controls open on the document body (Heimdall 0.14 portals the class
 * picker's options there), so a class can be picked with the mouse.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { ReviewSourcePane } from "../ReviewSourcePane";

function renderPane(onDismissPopover: () => void) {
  return render(
    <ReviewSourcePane
      title="Note"
      text="The Router sends requests."
      spans={[]}
      verdictOf={() => "awaiting"}
      titleOf={(id) => id}
      onSelect={vi.fn()}
      popoverAnchor={{ top: 10, left: 10 }}
      onDismissPopover={onDismissPopover}
      popover={
        <div>
          <input role="combobox" aria-controls="class-options" aria-expanded="true" />
        </div>
      }
    />,
  );
}

afterEach(() => {
  document.getElementById("class-options")?.remove();
});

describe("the add form's outside press", () => {
  it("doesn't close the form for a press in a list its controls open on the body", () => {
    const onDismiss = vi.fn();
    renderPane(onDismiss);
    const list = document.createElement("ul");
    list.id = "class-options";
    list.setAttribute("role", "listbox");
    const option = document.createElement("li");
    option.setAttribute("role", "option");
    list.append(option);
    document.body.append(list);
    fireEvent.mouseDown(option);
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("closes it for a press anywhere else outside", () => {
    const onDismiss = vi.fn();
    renderPane(onDismiss);
    fireEvent.mouseDown(document.body);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("keeps it for a press inside the form", () => {
    const onDismiss = vi.fn();
    renderPane(onDismiss);
    fireEvent.mouseDown(screen.getByRole("combobox"));
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
