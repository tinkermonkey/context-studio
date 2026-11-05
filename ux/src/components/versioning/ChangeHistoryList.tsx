import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Chip } from "@tinkermonkey/heimdall-ui";
import { useChanges } from "@/api/hooks/versioning";
import { formatRelativeTime } from "@/utils/formatters";
import { COPY } from "@/routes/app/versioning/copy";

function getOperationChip(operation: string) {
  const variantMap: Record<string, "cyan" | "violet" | "rose" | "neutral"> = {
    create: "cyan",
    update: "violet",
    delete: "rose",
  };
  const variant = variantMap[operation] ?? "neutral";
  return <Chip variant={variant}>{operation}</Chip>;
}

const ROW_COLUMNS = "1fr 100px 140px";

export function ChangeHistoryList() {
  const { data, isLoading, error, refetch } = useChanges();
  const changes = data?.events ?? [];

  if (isLoading) {
    return (
      <div className="stack-lg" style={{ flex: 1, overflow: "auto" }}>
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="skeleton"
            style={{ height: "48px", borderRadius: "var(--radius-md, 6px)" }}
          />
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorBanner error={error} onRetry={refetch} message={COPY.couldNotLoadChanges} />;
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
        <p style={{ margin: 0, fontSize: "13px" }}>{COPY.noChanges}</p>
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
      data-testid="change-history-list"
      role="list"
      aria-label={COPY.changesHeading}
    >
      <div
        aria-hidden="true"
        style={{
          display: "grid",
          gridTemplateColumns: ROW_COLUMNS,
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
        <div>Entity</div>
        <div>Type</div>
        <div>Time</div>
      </div>

      {changes.map((change) => {
        const label =
          typeof change.new_state?.title === "string" ? change.new_state.title : change.entity_id;
        return (
          <div
            key={change.id}
            role="listitem"
            style={{
              display: "grid",
              gridTemplateColumns: ROW_COLUMNS,
              gap: "8px",
              padding: "12px",
              borderBottom: "1px solid var(--canvas-border)",
              alignItems: "center",
            }}
            data-testid={`change-history-row-${change.id}`}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
              {getOperationChip(change.operation)}
              <span
                style={{
                  fontSize: "13px",
                  color: "rgb(var(--canvas-fg-1))",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
                title={label}
              >
                {label}
              </span>
            </div>

            <div>
              <Chip variant="neutral">{change.entity_type}</Chip>
            </div>

            <div style={{ fontSize: "12px", color: "var(--canvas-fg-3)", textAlign: "right" }}>
              {formatRelativeTime(change.timestamp)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
