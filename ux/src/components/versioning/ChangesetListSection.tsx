import { useState } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@/components/ui/Button";
import { useChangesets, useApplyChangeset } from "@/api/hooks/versioning";
import { useToasts } from "@/components/ui/Toast";
import { formatRelativeTime } from "@/utils/formatters";
import type { components } from "@/api/types";

type ChangesetResponse = components["schemas"]["ChangesetResponse"];

interface ChangesetListSectionProps {
  onApplyError?: (message: string) => void;
}

function getStateChip(state: string) {
  let bgColor = "var(--canvas-bg-2)";
  let textColor = "var(--canvas-fg-2)";

  switch (state) {
    case "working":
      bgColor = "#DBEAFE"; // blue-100
      textColor = "#1E40AF"; // blue-800
      break;
    case "staged":
      bgColor = "#FEF3C7"; // amber-100
      textColor = "#92400E"; // amber-800
      break;
    case "proposed":
      bgColor = "#DDD6FE"; // indigo-100
      textColor = "#4F46E5"; // indigo-600
      break;
    case "approved":
      bgColor = "#D1FAE5"; // emerald-100
      textColor = "#065F46"; // emerald-900
      break;
    case "merged":
      bgColor = "#CCFBF1"; // teal-100
      textColor = "#0D9488"; // teal-600
      break;
  }

  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        backgroundColor: bgColor,
        color: textColor,
      }}
    >
      {state}
    </span>
  );
}

export function ChangesetListSection({ onApplyError }: ChangesetListSectionProps) {
  const { toast } = useToasts();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const {
    data: changesets,
    isLoading,
    error,
    refetch,
  } = useChangesets();

  const applyMutation = useApplyChangeset();

  const handleApply = async (changesetId: string) => {
    try {
      await applyMutation.mutateAsync(changesetId);
      toast("success", "Changeset applied successfully");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to apply changeset";
      onApplyError?.(message);
      toast("error", message);
    }
  };

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
      <ErrorBanner error={error} onRetry={refetch} message="Could not load changesets" />
    );
  }

  if (!changesets || changesets.length === 0) {
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
          <p style={{ margin: "0 0 8px 0", fontSize: "13px" }}>No changesets yet</p>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--canvas-fg-3)" }}>
            Create your first changeset by staging pending changes
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
      data-testid="changeset-list"
    >
      {changesets.map((changeset, index) => (
        <div key={changeset.id}>
          {/* Changeset row */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 60px 120px 80px",
              gap: "8px",
              padding: "12px",
              borderBottom: "1px solid var(--canvas-border)",
              alignItems: "center",
              backgroundColor: "var(--canvas-bg)",
              cursor: "pointer",
            }}
            onClick={() => setExpandedId(expandedId === changeset.id ? null : changeset.id)}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: "13px", fontWeight: 500, color: "var(--canvas-fg)" }}>
                {changeset.name}
              </div>
              {changeset.description && (
                <div style={{ fontSize: "12px", color: "var(--canvas-fg-3)" }}>
                  {changeset.description}
                </div>
              )}
            </div>

            <div
              style={{
                fontSize: "12px",
                fontFamily: "var(--mono)",
                color: "var(--canvas-fg-2)",
                textAlign: "center",
              }}
            >
              {changeset.event_ids?.length || 0}
            </div>

            <div style={{ fontSize: "12px", color: "var(--canvas-fg-3)", textAlign: "center" }}>
              {formatRelativeTime(changeset.created_at)}
            </div>

            <div style={{ display: "flex", gap: "4px", justifyContent: "flex-end" }}>
              {getStateChip(changeset.state)}
            </div>
          </div>

          {/* Expanded detail row */}
          {expandedId === changeset.id && (
            <div
              style={{
                padding: "12px",
                borderBottom: "1px solid var(--canvas-border)",
                backgroundColor: "var(--canvas-bg-2)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "12px", fontWeight: 500, color: "var(--canvas-fg-2)", marginBottom: "8px" }}>
                    Changes ({changeset.event_ids?.length || 0})
                  </div>
                  <div
                    style={{
                      fontSize: "11px",
                      color: "var(--canvas-fg-3)",
                      fontFamily: "var(--mono)",
                    }}
                  >
                    {changeset.event_ids && changeset.event_ids.length > 0
                      ? changeset.event_ids.map((id) => (
                        <div key={id} style={{ marginBottom: "4px" }}>
                          {id.slice(0, 8)}...
                        </div>
                      ))
                      : "No changes"}
                  </div>
                </div>

                {(changeset.state as string) !== "merged" && (
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleApply(changeset.id);
                    }}
                    disabled={(changeset.state as string) === "merged" || applyMutation.isPending}
                    variant="primary"
                    size="sm"
                  >
                    {applyMutation.isPending ? "Applying..." : "Apply"}
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
