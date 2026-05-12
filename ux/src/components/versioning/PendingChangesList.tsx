import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { formatRelativeTime } from "@/utils/formatters";
import { COPY } from "@/routes/app/versioning/copy";
import type { components } from "@/api/types";

type VersioningChangeEventResponse = components["schemas"]["VersioningChangeEventResponse"];

interface PendingChangesListProps {
  changes: VersioningChangeEventResponse[];
  selectedIds: Set<string>;
  isLoading: boolean;
  error: Error | null | undefined;
  onSelectChange: (changeId: string, selected: boolean) => void;
  onSelectAll: (selected: boolean) => void;
  onRetry: () => void;
}

function getOperationColor(operation: string): string {
  switch (operation) {
    case "create":
      return "var(--accent-cyan, #22D3EE)";
    case "update":
      return "var(--accent-violet, #A78BFA)";
    case "delete":
      return "var(--accent-rose, #F87171)";
    default:
      return "var(--canvas-fg-3)";
  }
}

function getOperationChip(operation: string) {
  return (
    <span
      className="chip"
      style={{
        backgroundColor: getOperationColor(operation),
        color: "white",
      }}
    >
      {operation}
    </span>
  );
}

function getEntityTypeChip(entityType: string) {
  return (
    <span className="chip">
      {entityType}
    </span>
  );
}

export function PendingChangesList({
  changes,
  selectedIds,
  isLoading,
  error,
  onSelectChange,
  onSelectAll,
  onRetry,
}: PendingChangesListProps) {
  if (isLoading) {
    return (
      <div className="stack-lg" style={{ flex: 1, overflow: "auto" }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} height="48px" style={{ borderRadius: "var(--radius-md, 6px)" }} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <ErrorBanner error={error} onRetry={onRetry} message={COPY.noPendingChangesLoaded} />
    );
  }

  if (changes.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--canvas-fg-3)",
          textAlign: "center",
          padding: "20px",
        }}
      >
        <div>
          <p style={{ margin: "0 0 8px 0", fontSize: "13px" }}>{COPY.noPendingChanges}</p>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--canvas-fg-3)" }}>
            {COPY.allChangesStaged}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        flex: 1,
        overflow: "auto",
        border: "1px solid var(--canvas-border)",
        borderRadius: "var(--radius-lg, 8px)",
      }}
      data-testid="pending-changes-list"
    >
      {/* Header with select all */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "40px 1fr 100px 140px",
          gap: "8px",
          padding: "12px",
          borderBottom: "1px solid var(--canvas-border)",
          backgroundColor: "var(--canvas-bg-2)",
          fontSize: "11px",
          fontWeight: 600,
          textTransform: "uppercase",
          color: "var(--canvas-fg-3)",
          letterSpacing: "0.05em",
          position: "sticky",
          top: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <input
            type="checkbox"
            checked={selectedIds.size === changes.length && changes.length > 0}
            onChange={(e) => onSelectAll(e.target.checked)}
            style={{ cursor: "pointer" }}
            aria-label="Select all changes"
          />
        </div>
        <div>Entity</div>
        <div>Type</div>
        <div>Time</div>
      </div>

      {/* Changes list */}
      {changes.map((change) => (
        <div
          key={change.id}
          style={{
            display: "grid",
            gridTemplateColumns: "40px 1fr 100px 140px",
            gap: "8px",
            padding: "12px",
            borderBottom: "1px solid var(--canvas-border)",
            alignItems: "center",
            backgroundColor: selectedIds.has(change.id)
              ? "var(--canvas-bg-2)"
              : "var(--canvas-bg)",
          }}
          data-testid={`pending-change-${change.id}`}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
            <input
              type="checkbox"
              checked={selectedIds.has(change.id)}
              onChange={(e) => onSelectChange(change.id, e.target.checked)}
              style={{ cursor: "pointer" }}
              aria-label={`Select change ${change.id}`}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
            {getOperationChip(change.operation)}
            <span
              style={{
                fontSize: "13px",
                color: "var(--canvas-fg)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={
                typeof change.new_state?.title === "string"
                  ? change.new_state.title
                  : change.entity_id
              }
            >
              {typeof change.new_state?.title === "string"
                ? change.new_state.title
                : change.entity_id}
            </span>
          </div>

          <div>{getEntityTypeChip(change.entity_type)}</div>

          <div style={{ fontSize: "12px", color: "var(--canvas-fg-3)", textAlign: "right" }}>
            {formatRelativeTime(change.timestamp)}
          </div>
        </div>
      ))}
    </div>
  );
}
