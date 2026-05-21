import { useState } from "react";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useChangesets, useApplyChangeset } from "@/api/hooks/versioning";
import { useToasts } from "@/components/ui/Toast";
import { formatRelativeTime } from "@/utils/formatters";
import { COPY } from "@/routes/app/versioning/copy";

interface ChangesetListSectionProps {
  onApplyError?: (message: string) => void;
  onConflictDetected?: () => void;
}

function getStateChip(state: string) {
  const chipClasses: Record<string, { bg: string; text: string }> = {
    working: {
      bg: "var(--accent-blue-bg, #DBEAFE)",
      text: "var(--accent-blue, #1E40AF)",
    },
    staged: {
      bg: "var(--accent-amber-bg, #FEF3C7)",
      text: "var(--accent-amber, #92400E)",
    },
    proposed: {
      bg: "var(--accent-indigo-bg, #DDD6FE)",
      text: "var(--accent-indigo, #4F46E5)",
    },
    approved: {
      bg: "var(--accent-emerald-bg, #D1FAE5)",
      text: "var(--accent-emerald, #065F46)",
    },
    merged: {
      bg: "var(--accent-teal-bg, #CCFBF1)",
      text: "var(--accent-teal, #0D9488)",
    },
  };

  const colors = chipClasses[state] || {
    bg: "var(--canvas-bg-2)",
    text: "var(--canvas-fg-2)",
  };

  return (
    <span
      className="chip"
      style={{
        backgroundColor: colors.bg,
        color: colors.text,
      }}
    >
      {state}
    </span>
  );
}

export function ChangesetListSection({
  onApplyError,
  onConflictDetected,
}: ChangesetListSectionProps) {
  const { toast } = useToasts();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: changesets, isLoading, error, refetch } = useChangesets();

  const applyMutation = useApplyChangeset();

  const handleApply = async (changesetId: string) => {
    try {
      await applyMutation.mutateAsync(changesetId);
      toast("success", COPY.changesetAppliedSuccess);
    } catch (err) {
      const message = err instanceof Error ? err.message : COPY.failedToApplyChangeset;
      const isConflict = message.toLowerCase().includes("conflict");

      if (isConflict) {
        onConflictDetected?.();
      }

      if (onApplyError) {
        onApplyError(message);
      } else {
        toast("error", message);
      }
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
    return <ErrorBanner error={error} onRetry={refetch} message={COPY.couldNotLoadChangesets} />;
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
          <p style={{ margin: "0 0 8px 0", fontSize: "13px" }}>{COPY.noChangesetsYet}</p>
          <p style={{ margin: 0, fontSize: "12px", color: "var(--canvas-fg-3)" }}>
            {COPY.createFirstChangesetMessage}
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
      {changesets.map((changeset) => (
        <div key={changeset.id}>
          {/* Changeset row */}
          <div
            role="button"
            tabIndex={0}
            aria-expanded={expandedId === changeset.id}
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
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                setExpandedId(expandedId === changeset.id ? null : changeset.id);
              }
            }}
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
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                  gap: "12px",
                }}
              >
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      fontSize: "12px",
                      fontWeight: 500,
                      color: "var(--canvas-fg-2)",
                      marginBottom: "8px",
                    }}
                  >
                    {COPY.changesHeading(changeset.event_ids?.length || 0)}
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
                      : COPY.noChanges}
                  </div>
                </div>

                {changeset.state !== "merged" && (
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleApply(changeset.id);
                    }}
                    disabled={applyMutation.isPending}
                    variant="primary"
                    size="sm"
                  >
                    {applyMutation.isPending ? COPY.applyingButton : COPY.applyButton}
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
