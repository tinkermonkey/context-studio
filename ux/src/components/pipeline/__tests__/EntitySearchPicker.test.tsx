import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EntitySearchPicker } from "../EntitySearchPicker";

const lookup = vi.hoisted(() => ({ items: [] as Array<{ id: string; title?: string }> }));

vi.mock("@tinkermonkey/heimdall-ui", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tinkermonkey/heimdall-ui")>()),
  EntityPicker: () => <input aria-label="entity search" />,
}));

vi.mock("@/api/hooks/ontology/useEntityTypeQuery", () => ({
  useEntityTypeQuery: () => ({ data: { items: [] }, isError: false, error: null }),
  // The id lookup only knows about whatever the test puts in `lookup.items`,
  // standing in for a request that has not returned yet.
  useEntitiesById: () => ({ data: { items: lookup.items }, isError: false, error: null }),
}));

describe("EntitySearchPicker multi-select", () => {
  beforeEach(() => {
    lookup.items = [];
  });

  it("keeps earlier picks whose id lookup has not resolved yet", async () => {
    const onSelectMultiple = vi.fn();
    render(
      <EntitySearchPicker
        entityType="Class"
        multiSelect
        selectedIds={["class-a"]}
        onSelectMultiple={onSelectMultiple}
        data-testid="schema-grounding-nodes"
      />,
    );

    // class-a is selected but its lookup is still empty; it must still be listed...
    expect(screen.getByTestId("schema-grounding-nodes-list")).toHaveTextContent("class-a");

    // ...and removing it emits the remaining selection.
    await userEvent.click(screen.getByRole("button", { name: "Remove class-a" }));
    expect(onSelectMultiple).toHaveBeenLastCalledWith([]);
  });

  it("labels selected entities from the id lookup once it resolves", () => {
    lookup.items = [{ id: "class-a", title: "Threat" }];
    render(
      <EntitySearchPicker
        entityType="Class"
        multiSelect
        selectedIds={["class-a", "class-b"]}
        onSelectMultiple={vi.fn()}
        data-testid="schema-grounding-nodes"
      />,
    );

    const list = screen.getByTestId("schema-grounding-nodes-list");
    expect(list).toHaveTextContent("Threat");
    // An id the lookup did not return is kept, shown by id, not dropped.
    expect(list).toHaveTextContent("class-b");
  });
});
