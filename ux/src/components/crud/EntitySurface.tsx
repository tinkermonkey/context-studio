import {
  useState,
  useRef,
  useImperativeHandle,
  forwardRef,
  type ReactNode,
} from "react";
import { Button, Icon, Modal, SegmentedControl, Select } from "@tinkermonkey/heimdall-ui";
import type { Column } from "@tinkermonkey/heimdall-ui";
import { SelectableTable } from "./SelectableTable";
import type { RowMenuAction } from "./SelectableTable";
import { CreateDrawer } from "./CreateDrawer";
import type { EntityType, FormValues } from "./CreateDrawer";
import { BulkBar } from "./BulkBar";
import type { BulkBarAction } from "./BulkBar";
import { CascadeDeleteDialog } from "./CascadeDeleteDialog";
import type { CascadeImpactData } from "./CascadeDeleteDialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { pluralize } from "./utils";

export type { EntityType, FormValues };

const ENTITY_ICON: Record<EntityType, string> = {
  taxonomy: "schema",
  scheme: "layout",
  class: "component",
  property: "link",
  individual: "user",
  relationship: "arrowRight",
};

export interface EntitySurfaceHandle {
  startCreate(ctx?: Partial<FormValues>): void;
}

export interface EntitySurfaceBulkAction extends BulkBarAction {
  fieldLabel?: string;
  options?: Array<{ value: string; label: string }>;
  onBulkConfirm?: (ids: string[], value: string) => Promise<void>;
}

interface EntitySurfaceProps<T extends { id: string }> {
  entityType: EntityType;
  entityLabel?: string;
  data: T[];
  isLoading?: boolean;
  columns: Column<T>[];
  renderInspector: (entity: T) => ReactNode;
  rowMenuActions?: RowMenuAction[];
  onRowMenuAction?: (actionId: string, entity: T) => void;
  getDuplicateContext?: (entity: T) => Partial<FormValues>;
  onDeleteEntity?: (ids: string[]) => Promise<void>;
  getCascadeImpact?: (ids: string[]) => Promise<CascadeImpactData>;
  bulkActions?: EntitySurfaceBulkAction[];
  initialTaxonomyId?: string;
  initialSchemeId?: string;
  onCreateSuccess?: (entity: { id: string; title?: string }) => void;
  inspectorWidth?: number;
  testId?: string;
}

function defaultDuplicateContext<T extends { id: string }>(entity: T): Partial<FormValues> {
  const e = entity as Record<string, unknown>;
  const title = typeof e.title === "string" ? e.title : "";
  const identifier = typeof e.identifier === "string" ? e.identifier : "";
  return {
    title: title ? `${title} (copy)` : "(copy)",
    ...(identifier ? { identifier: `${identifier}_copy` } : {}),
    description: typeof e.description === "string" ? e.description : undefined,
  };
}

function EntitySurfaceBase<T extends { id: string }>(
  {
    entityType,
    entityLabel,
    data,
    isLoading,
    columns,
    renderInspector,
    rowMenuActions,
    onRowMenuAction,
    getDuplicateContext,
    onDeleteEntity,
    getCascadeImpact,
    bulkActions = [],
    initialTaxonomyId,
    initialSchemeId,
    onCreateSuccess,
    inspectorWidth = 420,
    testId,
  }: EntitySurfaceProps<T>,
  ref: React.ForwardedRef<EntitySurfaceHandle>,
) {
  const label = entityLabel ?? entityType;
  const icon = ENTITY_ICON[entityType] ?? "component";

  // Mode and create context
  const [mode, setMode] = useState<"view" | "create">("view");
  const [createContext, setCreateContext] = useState<Partial<FormValues>>({});
  const [identifierDirty, setIdentifierDirty] = useState(false);

  // Inspector selection (set by row click)
  const [inspectorId, setInspectorId] = useState<string | undefined>(undefined);

  // Bulk selection (set by checkboxes)
  const [selectedRows, setSelectedRows] = useState<string[]>([]);

  // Delete state
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; label: string } | null>(null);
  const [deleteIds, setDeleteIds] = useState<string[] | null>(null);
  const [cascadeImpact, setCascadeImpact] = useState<CascadeImpactData | undefined>(undefined);
  const [isDeleting, setIsDeleting] = useState(false);
  const deleteDialogOpen = deleteTarget !== null || deleteIds !== null;

  // Bulk modal state
  const [activeBulkAction, setActiveBulkAction] = useState<EntitySurfaceBulkAction | null>(null);
  const [bulkModalValue, setBulkModalValue] = useState("");
  const [isApplyingBulk, setIsApplyingBulk] = useState(false);

  // Track last deleted to deselect after confirm
  const pendingDeleteIdsRef = useRef<string[]>([]);

  // Imperative handle
  useImperativeHandle(ref, () => ({
    startCreate(ctx?: Partial<FormValues>) {
      setCreateContext(ctx ?? {});
      setIdentifierDirty(!!(ctx?.identifier));
      setMode("create");
    },
  }));

  // ── Handlers ──────────────────────────────────────────────────────────────

  function openDeleteForIds(ids: string[], label?: string) {
    pendingDeleteIdsRef.current = ids;
    if (ids.length === 1) {
      const entity = data.find((d) => d.id === ids[0]);
      const entityLabel =
        label ??
        (entity ? (entity as Record<string, unknown>).title as string ?? entity.id : ids[0]);
      setDeleteTarget({ id: ids[0], label: entityLabel });
      setDeleteIds(null);
    } else {
      setDeleteTarget(null);
      setDeleteIds(ids);
    }
    setCascadeImpact(undefined);
    if (getCascadeImpact) {
      getCascadeImpact(ids).then(setCascadeImpact).catch(() => undefined);
    }
  }

  function closeDeleteDialog() {
    setDeleteTarget(null);
    setDeleteIds(null);
    setCascadeImpact(undefined);
    pendingDeleteIdsRef.current = [];
  }

  async function handleDeleteConfirm() {
    if (!onDeleteEntity) return;
    setIsDeleting(true);
    try {
      await onDeleteEntity(pendingDeleteIdsRef.current);
      // Deselect deleted entities
      const deleted = new Set(pendingDeleteIdsRef.current);
      setSelectedRows((prev) => prev.filter((id) => !deleted.has(id)));
      if (inspectorId && deleted.has(inspectorId)) {
        setInspectorId(undefined);
      }
      closeDeleteDialog();
    } finally {
      setIsDeleting(false);
    }
  }

  function handleRowMenuAction(actionId: string, entity: T) {
    if (actionId === "delete") {
      openDeleteForIds([entity.id]);
    } else if (actionId === "duplicate") {
      const ctx = getDuplicateContext
        ? getDuplicateContext(entity)
        : defaultDuplicateContext(entity);
      setCreateContext(ctx);
      setIdentifierDirty(!!(ctx.identifier));
      setMode("create");
    } else {
      onRowMenuAction?.(actionId, entity);
    }
  }

  function handleBulkAction(actionId: string) {
    if (actionId === "delete") {
      openDeleteForIds(selectedRows);
      return;
    }

    const action = bulkActions.find((a) => a.id === actionId);
    if (!action) return;

    // Non-delete bulk op → open value-selection modal
    if (action.onBulkConfirm) {
      setActiveBulkAction(action);
      setBulkModalValue(action.options?.[0]?.value ?? "");
    }
  }

  async function handleBulkModalConfirm() {
    if (!activeBulkAction?.onBulkConfirm) return;
    setIsApplyingBulk(true);
    try {
      await activeBulkAction.onBulkConfirm(selectedRows, bulkModalValue);
      setSelectedRows([]);
      setActiveBulkAction(null);
    } finally {
      setIsApplyingBulk(false);
    }
  }

  function handleCreateSuccess(entity: { id: string; title?: string }) {
    setMode("view");
    setInspectorId(entity.id);
    onCreateSuccess?.(entity);
  }

  // ── Derived values ─────────────────────────────────────────────────────────

  const inspectorEntity = inspectorId ? data.find((d) => d.id === inspectorId) : undefined;
  const showRight = mode === "create" || !!inspectorEntity;

  // ── Empty state ────────────────────────────────────────────────────────────

  if (data.length === 0 && !isLoading && mode === "view") {
    return (
      <div data-testid={testId ?? "entity-surface"}>
        <EmptyState
          icon={<Icon name={icon as any} size={22} />}
          title={`No ${label}s yet`}
          description={`Create your first ${label} to get started.`}
          action={{
            label: `New ${label}`,
            onClick: () => {
              setCreateContext({});
              setIdentifierDirty(false);
              setMode("create");
            },
          }}
        />
      </div>
    );
  }

  // ── Main layout ────────────────────────────────────────────────────────────

  return (
    <div
      data-testid={testId ?? "entity-surface"}
      style={{
        display: "grid",
        gridTemplateColumns: showRight ? `1fr ${inspectorWidth}px` : "1fr",
        gap: 14,
        alignItems: "start",
      }}
    >
      {/* Left: table */}
      <div>
        <SelectableTable
          columns={columns}
          data={data}
          isLoading={isLoading}
          selectedRows={selectedRows}
          onSelectRows={setSelectedRows}
          onRowClick={(row) => {
            setInspectorId(row.id);
            if (mode === "create") setMode("view");
          }}
          rowMenuActions={rowMenuActions}
          onRowMenuAction={handleRowMenuAction}
        />
      </div>

      {/* Right: inline CreateDrawer or entity inspector */}
      {showRight && (
        <div>
          {mode === "create" ? (
            <CreateDrawer
              entityType={entityType}
              isOpen
              onClose={() => setMode("view")}
              variant="inline"
              initialValues={createContext}
              initialIdentifierDirty={identifierDirty}
              initialTaxonomyId={createContext.taxonomyId ?? initialTaxonomyId}
              initialSchemeId={createContext.schemeId ?? initialSchemeId}
              onSuccess={handleCreateSuccess}
              data-testid="entity-surface-create-drawer"
            />
          ) : inspectorEntity ? (
            renderInspector(inspectorEntity)
          ) : null}
        </div>
      )}

      {/* Floating bulk bar */}
      {selectedRows.length > 0 && (
        <BulkBar
          count={selectedRows.length}
          entityLabel={label}
          actions={bulkActions}
          onAction={handleBulkAction}
          onClear={() => setSelectedRows([])}
        />
      )}

      {/* Single / bulk delete dialog */}
      <CascadeDeleteDialog
        isOpen={deleteDialogOpen}
        onClose={closeDeleteDialog}
        onConfirm={() => void handleDeleteConfirm()}
        target={deleteTarget ?? undefined}
        ids={deleteIds ?? undefined}
        entityType={label}
        impactData={cascadeImpact}
        isDeleting={isDeleting}
      />

      {/* Non-delete bulk op value-selection modal */}
      {activeBulkAction && (
        <Modal
          isOpen={!!activeBulkAction}
          onClose={() => setActiveBulkAction(null)}
          title={`Apply: ${activeBulkAction.label}`}
          size="sm"
          footer={
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <Button
                variant="ghost"
                onClick={() => setActiveBulkAction(null)}
                disabled={isApplyingBulk}
                data-testid="bulk-modal-cancel"
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={() => void handleBulkModalConfirm()}
                disabled={isApplyingBulk}
                data-testid="bulk-modal-confirm"
              >
                {isApplyingBulk
                  ? "Applying…"
                  : `Apply to ${selectedRows.length} ${pluralize(label, selectedRows.length)}`}
              </Button>
            </div>
          }
        >
          <div className="stack">
            {activeBulkAction.fieldLabel && (
              <div className="field-label">{activeBulkAction.fieldLabel}</div>
            )}
            {activeBulkAction.options && activeBulkAction.options.length > 0 ? (
              activeBulkAction.options.length <= 4 ? (
                <SegmentedControl
                  value={bulkModalValue}
                  onChange={(v) => setBulkModalValue(v as string)}
                  options={activeBulkAction.options}
                  data-testid="bulk-modal-segmented"
                />
              ) : (
                <Select
                  value={bulkModalValue}
                  onChange={(v) => setBulkModalValue(v)}
                  data-testid="bulk-modal-select"
                >
                  {activeBulkAction.options.map((o) => (
                    <Select.Item key={o.value} value={o.value}>
                      {o.label}
                    </Select.Item>
                  ))}
                </Select>
              )
            ) : null}
          </div>
        </Modal>
      )}
    </div>
  );
}

export const EntitySurface = forwardRef(EntitySurfaceBase) as <T extends { id: string }>(
  props: EntitySurfaceProps<T> & React.RefAttributes<EntitySurfaceHandle>
) => React.ReactElement | null;
