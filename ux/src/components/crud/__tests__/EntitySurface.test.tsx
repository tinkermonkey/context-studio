import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createRef } from "react";
import { render } from "@/test/test-utils";
import { EntitySurface, type EntitySurfaceHandle } from "../EntitySurface";
import type { Column } from "@tinkermonkey/heimdall-ui";

// Isolate container logic — sub-components are tested separately
vi.mock("../CreateDrawer", () => ({
  CreateDrawer: ({
    isOpen,
    onClose,
    onSuccess,
    initialValues,
    initialIdentifierDirty,
    "data-testid": testId,
  }: any) => {
    if (!isOpen) return null;
    return (
      <div data-testid={testId ?? "create-drawer"}>
        <div data-testid="create-drawer-initial-values">{JSON.stringify(initialValues)}</div>
        <div data-testid="create-drawer-identifier-dirty">{String(initialIdentifierDirty)}</div>
        <button onClick={onClose} data-testid="create-drawer-cancel">
          Cancel
        </button>
        <button
          onClick={() => onSuccess?.({ id: "new-id-1", title: "New Entity" })}
          data-testid="create-drawer-submit"
        >
          Create
        </button>
      </div>
    );
  },
}));

vi.mock("../SelectableTable", () => ({
  SelectableTable: ({
    data,
    selectedRows = [],
    onSelectRows,
    onRowClick,
    onRowMenuAction,
    rowMenuActions,
  }: any) => (
    <div data-testid="selectable-table">
      {data.map((row: any) => (
        <div key={row.id} data-testid={`row-${row.id}`}>
          <input
            type="checkbox"
            aria-label={`Select ${row.id}`}
            checked={selectedRows.includes(row.id)}
            onChange={(e) => {
              const next = e.target.checked
                ? [...selectedRows, row.id]
                : selectedRows.filter((id: string) => id !== row.id);
              onSelectRows?.(next);
            }}
            data-testid={`checkbox-${row.id}`}
          />
          <span onClick={() => onRowClick?.(row)} data-testid={`click-${row.id}`}>
            {row.title}
          </span>
          {rowMenuActions?.map((action: any) => (
            <button
              key={action.id}
              onClick={() => onRowMenuAction?.(action.id, row)}
              data-testid={`action-${action.id}-${row.id}`}
            >
              {action.label}
            </button>
          ))}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("../BulkBar", () => ({
  BulkBar: ({ count, actions = [], onAction, onClear }: any) =>
    count > 0 ? (
      <div data-testid="bulk-bar">
        <span data-testid="bulk-count">{count}</span>
        {actions.map((action: any) => (
          <button
            key={action.id}
            onClick={() => onAction(action.id)}
            data-testid={`bulk-action-${action.id}`}
          >
            {action.label}
          </button>
        ))}
        <button onClick={onClear} data-testid="bulk-clear">
          Clear
        </button>
      </div>
    ) : null,
}));

vi.mock("../CascadeDeleteDialog", () => ({
  CascadeDeleteDialog: ({ isOpen, onClose, onConfirm, target, ids }: any) => {
    if (!isOpen) return null;
    return (
      <div data-testid="cascade-delete-dialog">
        {target && <span data-testid="delete-target-label">{target.label}</span>}
        {ids && <span data-testid="delete-ids-count">{ids.length}</span>}
        <button onClick={onConfirm} data-testid="cascade-confirm">
          Confirm
        </button>
        <button onClick={onClose} data-testid="cascade-cancel">
          Cancel
        </button>
      </div>
    );
  },
}));

interface TestRow {
  id: string;
  title: string;
  identifier: string;
}

const columns: Column<TestRow>[] = [{ key: "title", label: "Title" }];

function makeRows(count: number): TestRow[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `row-${i + 1}`,
    title: `Entity ${i + 1}`,
    identifier: `entity_${i + 1}`,
  }));
}

function renderSurface(props: Record<string, any> = {}) {
  const ref = createRef<EntitySurfaceHandle>();
  const result = render(
    <EntitySurface
      ref={ref}
      entityType="taxonomy"
      data={makeRows(3)}
      columns={columns}
      renderInspector={(entity) => <div data-testid="inspector">{(entity as TestRow).title}</div>}
      {...props}
    />,
  );
  return { ...result, ref };
}

describe("EntitySurface", () => {
  describe("data-testid", () => {
    it("has default entity-surface testid", () => {
      renderSurface();
      expect(screen.getByTestId("entity-surface")).toBeInTheDocument();
    });

    it("accepts custom testId", () => {
      renderSurface({ testId: "my-surface" });
      expect(screen.getByTestId("my-surface")).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("renders empty state when data is empty in view mode", () => {
      renderSurface({ data: [] });
      expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    });

    it("shows entity type CTA in empty state", () => {
      renderSurface({ data: [] });
      expect(screen.getByTestId("empty-state-action")).toHaveTextContent("New taxonomy");
    });

    it("clicking empty state CTA opens the create drawer", async () => {
      const user = userEvent.setup();
      renderSurface({ data: [] });
      await user.click(screen.getByTestId("empty-state-action"));
      expect(screen.getByTestId("entity-surface-create-drawer")).toBeInTheDocument();
    });

    it("does not render empty state when data is present", () => {
      renderSurface();
      expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
    });
  });

  describe("table rendering", () => {
    it("renders the selectable table", () => {
      renderSurface();
      expect(screen.getByTestId("selectable-table")).toBeInTheDocument();
    });

    it("passes all data rows to the table", () => {
      renderSurface();
      expect(screen.getByTestId("row-row-1")).toBeInTheDocument();
      expect(screen.getByTestId("row-row-2")).toBeInTheDocument();
      expect(screen.getByTestId("row-row-3")).toBeInTheDocument();
    });
  });

  describe("row click — inspector selection", () => {
    it("opens inspector when a row is clicked", async () => {
      const user = userEvent.setup();
      renderSurface();
      await user.click(screen.getByTestId("click-row-1"));
      expect(screen.getByTestId("inspector")).toHaveTextContent("Entity 1");
    });

    it("does not open inspector when only checkbox is clicked", async () => {
      const user = userEvent.setup();
      renderSurface();
      await user.click(screen.getByTestId("checkbox-row-1"));
      expect(screen.queryByTestId("inspector")).not.toBeInTheDocument();
    });

    it("clicking a different row updates the inspector without changing bulk selection", async () => {
      const user = userEvent.setup();
      renderSurface();
      await user.click(screen.getByTestId("checkbox-row-1"));
      await user.click(screen.getByTestId("click-row-2"));
      expect(screen.getByTestId("inspector")).toHaveTextContent("Entity 2");
      expect(screen.getByTestId("bulk-count")).toHaveTextContent("1");
    });
  });

  describe("create mode via ref", () => {
    it("opens create drawer when startCreate is called via ref", () => {
      const { ref } = renderSurface();
      act(() => ref.current?.startCreate());
      expect(screen.getByTestId("entity-surface-create-drawer")).toBeInTheDocument();
    });

    it("passes ctx to create drawer via ref", () => {
      const { ref } = renderSurface();
      act(() => ref.current?.startCreate({ title: "Prefilled" }));
      const vals = JSON.parse(
        screen.getByTestId("create-drawer-initial-values").textContent ?? "{}",
      );
      expect(vals.title).toBe("Prefilled");
    });

    it("uses explicit identifierDirty=false even when ctx.identifier is present", () => {
      const { ref } = renderSurface();
      act(() => ref.current?.startCreate({ identifier: "some_id" }, false));
      expect(screen.getByTestId("create-drawer-identifier-dirty")).toHaveTextContent("false");
    });

    it("infers identifierDirty=true from ctx.identifier when not provided", () => {
      const { ref } = renderSurface();
      act(() => ref.current?.startCreate({ identifier: "some_id" }));
      expect(screen.getByTestId("create-drawer-identifier-dirty")).toHaveTextContent("true");
    });

    it("infers identifierDirty=false when ctx has no identifier", () => {
      const { ref } = renderSurface();
      act(() => ref.current?.startCreate({ title: "No ID" }));
      expect(screen.getByTestId("create-drawer-identifier-dirty")).toHaveTextContent("false");
    });

    it("closing the create drawer returns to view mode", async () => {
      const user = userEvent.setup();
      const { ref } = renderSurface();
      act(() => ref.current?.startCreate());
      await user.click(screen.getByTestId("create-drawer-cancel"));
      expect(screen.queryByTestId("entity-surface-create-drawer")).not.toBeInTheDocument();
    });
  });

  describe("after successful creation", () => {
    it("closes create drawer after success", async () => {
      const user = userEvent.setup();
      const data = [...makeRows(3), { id: "new-id-1", title: "New Entity" }];
      const { ref } = renderSurface({ data });
      act(() => ref.current?.startCreate());
      await user.click(screen.getByTestId("create-drawer-submit"));
      expect(screen.queryByTestId("entity-surface-create-drawer")).not.toBeInTheDocument();
    });

    it("auto-selects the new entity in the inspector", async () => {
      const user = userEvent.setup();
      const data = [...makeRows(3), { id: "new-id-1", title: "New Entity" }];
      const { ref } = renderSurface({ data });
      act(() => ref.current?.startCreate());
      await user.click(screen.getByTestId("create-drawer-submit"));
      expect(screen.getByTestId("inspector")).toHaveTextContent("New Entity");
    });

    it("calls onCreateSuccess with the new entity", async () => {
      const user = userEvent.setup();
      const onCreateSuccess = vi.fn();
      const data = [...makeRows(3), { id: "new-id-1", title: "New Entity" }];
      const { ref } = renderSurface({ data, onCreateSuccess });
      act(() => ref.current?.startCreate());
      await user.click(screen.getByTestId("create-drawer-submit"));
      expect(onCreateSuccess).toHaveBeenCalledWith({ id: "new-id-1", title: "New Entity" });
    });
  });

  describe("bulk selection", () => {
    it("shows bulk bar when rows are checked", async () => {
      const user = userEvent.setup();
      renderSurface();
      await user.click(screen.getByTestId("checkbox-row-1"));
      expect(screen.getByTestId("bulk-bar")).toBeInTheDocument();
    });

    it("shows correct count in bulk bar", async () => {
      const user = userEvent.setup();
      renderSurface();
      await user.click(screen.getByTestId("checkbox-row-1"));
      await user.click(screen.getByTestId("checkbox-row-2"));
      expect(screen.getByTestId("bulk-count")).toHaveTextContent("2");
    });

    it("hides bulk bar after clear is clicked", async () => {
      const user = userEvent.setup();
      renderSurface();
      await user.click(screen.getByTestId("checkbox-row-1"));
      await user.click(screen.getByTestId("bulk-clear"));
      expect(screen.queryByTestId("bulk-bar")).not.toBeInTheDocument();
    });
  });

  describe("single delete", () => {
    const rowMenuActions = [{ id: "delete", label: "Delete" }];

    it("opens cascade delete dialog on delete action", async () => {
      const user = userEvent.setup();
      renderSurface({ rowMenuActions });
      await user.click(screen.getByTestId("action-delete-row-1"));
      expect(screen.getByTestId("cascade-delete-dialog")).toBeInTheDocument();
    });

    it("shows target entity label in dialog", async () => {
      const user = userEvent.setup();
      renderSurface({ rowMenuActions });
      await user.click(screen.getByTestId("action-delete-row-1"));
      expect(screen.getByTestId("delete-target-label")).toBeInTheDocument();
    });

    it("calls onDeleteEntity with entity id on confirm", async () => {
      const user = userEvent.setup();
      const onDeleteEntity = vi.fn().mockResolvedValue(undefined);
      renderSurface({ rowMenuActions, onDeleteEntity });
      await user.click(screen.getByTestId("action-delete-row-1"));
      await user.click(screen.getByTestId("cascade-confirm"));
      expect(onDeleteEntity).toHaveBeenCalledWith(["row-1"]);
    });

    it("closes dialog on cancel without deleting", async () => {
      const user = userEvent.setup();
      const onDeleteEntity = vi.fn().mockResolvedValue(undefined);
      renderSurface({ rowMenuActions, onDeleteEntity });
      await user.click(screen.getByTestId("action-delete-row-1"));
      await user.click(screen.getByTestId("cascade-cancel"));
      expect(screen.queryByTestId("cascade-delete-dialog")).not.toBeInTheDocument();
      expect(onDeleteEntity).not.toHaveBeenCalled();
    });

    it("deselects deleted entity from inspector after confirm", async () => {
      const user = userEvent.setup();
      const onDeleteEntity = vi.fn().mockResolvedValue(undefined);
      renderSurface({ rowMenuActions, onDeleteEntity });
      await user.click(screen.getByTestId("click-row-1"));
      expect(screen.getByTestId("inspector")).toBeInTheDocument();
      await user.click(screen.getByTestId("action-delete-row-1"));
      await user.click(screen.getByTestId("cascade-confirm"));
      await waitFor(() => expect(screen.queryByTestId("inspector")).not.toBeInTheDocument());
    });
  });

  describe("bulk delete", () => {
    const bulkDeleteActions = [{ id: "delete", label: "Delete", danger: true }];

    it("opens cascade delete dialog with ids array on bulk delete", async () => {
      const user = userEvent.setup();
      renderSurface({ bulkActions: bulkDeleteActions });
      await user.click(screen.getByTestId("checkbox-row-1"));
      await user.click(screen.getByTestId("checkbox-row-2"));
      await user.click(screen.getByTestId("bulk-action-delete"));
      expect(screen.getByTestId("cascade-delete-dialog")).toBeInTheDocument();
      expect(screen.getByTestId("delete-ids-count")).toHaveTextContent("2");
    });
  });

  describe("duplicate action", () => {
    const rowMenuActions = [{ id: "duplicate", label: "Duplicate" }];

    it("opens create drawer with _copy identifier", async () => {
      const user = userEvent.setup();
      renderSurface({ rowMenuActions });
      await user.click(screen.getByTestId("action-duplicate-row-1"));
      expect(screen.getByTestId("entity-surface-create-drawer")).toBeInTheDocument();
      const vals = JSON.parse(
        screen.getByTestId("create-drawer-initial-values").textContent ?? "{}",
      );
      expect(vals.identifier).toBe("entity_1_copy");
    });

    it("sets identifierDirty=true for duplicate", async () => {
      const user = userEvent.setup();
      renderSurface({ rowMenuActions });
      await user.click(screen.getByTestId("action-duplicate-row-1"));
      expect(screen.getByTestId("create-drawer-identifier-dirty")).toHaveTextContent("true");
    });
  });

  describe("non-delete bulk actions", () => {
    const onBulkConfirm = vi.fn().mockResolvedValue(undefined);
    const bulkActions = [
      {
        id: "set-relevance",
        label: "Set Relevance",
        fieldLabel: "Relevance",
        options: [
          { value: "relevant", label: "Relevant" },
          { value: "optional", label: "Optional" },
        ],
        onBulkConfirm,
      },
    ];

    beforeEach(() => {
      onBulkConfirm.mockClear();
    });

    it("opens value-selection modal on non-delete bulk action", async () => {
      const user = userEvent.setup();
      renderSurface({ bulkActions });
      await user.click(screen.getByTestId("checkbox-row-1"));
      await user.click(screen.getByTestId("bulk-action-set-relevance"));
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("confirm calls onBulkConfirm with selected ids and value", async () => {
      const user = userEvent.setup();
      renderSurface({ bulkActions });
      await user.click(screen.getByTestId("checkbox-row-1"));
      await user.click(screen.getByTestId("bulk-action-set-relevance"));
      await user.click(screen.getByTestId("bulk-modal-confirm"));
      await waitFor(() =>
        expect(onBulkConfirm).toHaveBeenCalledWith(["row-1"], expect.any(String)),
      );
    });

    it("cancel closes modal without calling onBulkConfirm", async () => {
      const user = userEvent.setup();
      renderSurface({ bulkActions });
      await user.click(screen.getByTestId("checkbox-row-1"));
      await user.click(screen.getByTestId("bulk-action-set-relevance"));
      await user.click(screen.getByTestId("bulk-modal-cancel"));
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(onBulkConfirm).not.toHaveBeenCalled();
    });
  });
});
