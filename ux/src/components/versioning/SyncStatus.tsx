import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Skeleton } from "@/components/ui/Skeleton";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useSyncStatus, usePushSync, usePullSync } from "@/api/hooks/versioning";
import { useConfig } from "@/api/hooks/admin";
import { useToasts } from "@/components/ui/Toast";
import { formatRelativeTime } from "@/utils/formatters";
import { COPY } from "@/routes/app/versioning/copy";
import type { components } from "@/api/types";

type SyncStatusResponse = components["schemas"]["SyncStatusResponse"];

interface SyncStatusPanelProps {
  onConflictDetected?: () => void;
}

function getStatusChip(status: string) {
  const chipMap: Record<string, string> = {
    synced: "emerald",
    ahead: "amber",
    behind: "amber",
    diverged: "rose",
    unknown: "gray",
  };

  const chipClass = chipMap[status] || "gray";

  return <span className={`chip ${chipClass}`}>{status}</span>;
}

function determineStatus(syncStatus: SyncStatusResponse): string {
  if (!syncStatus.is_configured || syncStatus.is_degraded) {
    return "unknown";
  }

  if (syncStatus.unprocessed_count > 0) {
    return "ahead";
  }

  if (syncStatus.last_pushed_at || syncStatus.last_pulled_at) {
    return "synced";
  }

  return "unknown";
}

function SyncStatusLoadingState() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", width: "100%" }}>
      <Skeleton height="200px" style={{ borderRadius: "var(--radius-lg, 8px)" }} />
      <Skeleton height="200px" style={{ borderRadius: "var(--radius-lg, 8px)" }} />
    </div>
  );
}

function SyncStatusCard({
  title,
  status,
  lastSyncTime,
  changeCount,
  isLoading,
  onAction,
}: {
  title: string;
  status: string;
  lastSyncTime?: string | null;
  changeCount?: number;
  isLoading: boolean;
  onAction: () => void;
}) {
  return (
    <div
      className="panel"
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
      }}
    >
      <div>
        <div style={{ padding: "16px", borderBottom: "1px solid var(--canvas-bd)" }}>
          <div style={{ fontSize: "13px", fontWeight: 600, marginBottom: "8px" }}>{title}</div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {getStatusChip(status)}
          </div>
        </div>

        <div style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          {lastSyncTime != null && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "12px", color: "var(--canvas-fg-3)" }}>
                {COPY.lastSyncLabel}
              </span>
              <span
                style={{
                  fontSize: "12px",
                  fontFamily: "var(--mono)",
                  color: "var(--canvas-fg-2)",
                }}
              >
                {formatRelativeTime(lastSyncTime)}
              </span>
            </div>
          )}

          {changeCount !== undefined && changeCount > 0 && (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "12px", color: "var(--canvas-fg-3)" }}>
                {title === COPY.pushCardTitle ? COPY.changesAheadLabel : COPY.changesPulledLabel}
              </span>
              <span
                style={{
                  fontSize: "12px",
                  fontFamily: "var(--mono)",
                  color: "var(--canvas-fg-2)",
                }}
              >
                {changeCount}
              </span>
            </div>
          )}
        </div>
      </div>

      <div style={{ padding: "12px 16px", borderTop: "1px solid var(--canvas-bd)" }}>
        {isLoading ? (
          <div
            style={{
              height: "32px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                width: "20px",
                height: "20px",
                border: "2px solid var(--canvas-fg-3)",
                borderTopColor: "var(--canvas-fg-1)",
                borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
              }}
            />
          </div>
        ) : (
          <Button variant="primary" size="md" onClick={onAction} style={{ width: "100%" }}>
            {title}
          </Button>
        )}
      </div>
    </div>
  );
}

export function SyncStatusPanel({ onConflictDetected }: SyncStatusPanelProps) {
  const { toast } = useToasts();
  const navigate = useNavigate();
  const [lastPullCount, setLastPullCount] = useState<number | undefined>();

  const {
    data: syncStatus,
    isLoading: syncStatusLoading,
    error: syncStatusError,
    refetch: refetchSyncStatus,
  } = useSyncStatus();

  const { data: config } = useConfig();

  const pushMutation = usePushSync();
  const pullMutation = usePullSync();

  const handlePush = async () => {
    try {
      const result = await pushMutation.mutateAsync();
      toast("success", COPY.pushSuccessMessage(result.pushed));
    } catch (error) {
      const message = error instanceof Error ? error.message : COPY.failedToPush;
      const isConflict = message.toLowerCase().includes("conflict");

      if (isConflict) {
        onConflictDetected?.();
      }

      toast("error", `${message}${COPY.retryErrorSuffix}`);
    }
  };

  const handlePull = async () => {
    try {
      const result = await pullMutation.mutateAsync();
      setLastPullCount(result.pulled);
      toast("success", COPY.pullSuccessMessage(result.pulled));
    } catch (error) {
      const message = error instanceof Error ? error.message : COPY.failedToPull;
      const isConflict = message.toLowerCase().includes("conflict");

      if (isConflict) {
        onConflictDetected?.();
      }

      toast("error", `${message}${COPY.retryErrorSuffix}`);
    }
  };

  const getSyncTargetUrl = (): string => {
    if (!config?.sections) return COPY.notConfiguredLabel;

    const syncSection = config.sections.sync as Record<string, unknown> | undefined;
    if (!syncSection) return COPY.notConfiguredLabel;

    return (
      (syncSection.target_path as string) ||
      (syncSection.s3_bucket as string) ||
      COPY.notConfiguredLabel
    );
  };

  if (syncStatusLoading) {
    return <SyncStatusLoadingState />;
  }

  if (syncStatusError) {
    return (
      <ErrorBanner
        error={syncStatusError}
        onRetry={refetchSyncStatus}
        message={COPY.couldNotLoadSyncStatus}
      />
    );
  }

  if (!syncStatus || !syncStatus.is_configured) {
    return (
      <EmptyState
        title={COPY.noSyncTargetConfigured}
        description={COPY.syncTargetDescription}
        action={{
          label: COPY.goToSettingsButton,
          onClick: () => navigate({ to: "/app/settings" }),
        }}
      />
    );
  }

  const status = determineStatus(syncStatus);

  return (
    <div
      data-testid="sync-status-panel"
      style={{ display: "flex", flexDirection: "column", gap: "24px" }}
    >
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
        <SyncStatusCard
          title={COPY.pushCardTitle}
          status={status === "ahead" ? "ahead" : "synced"}
          lastSyncTime={syncStatus.last_pushed_at}
          changeCount={syncStatus.unprocessed_count > 0 ? syncStatus.unprocessed_count : undefined}
          isLoading={pushMutation.isPending}
          onAction={handlePush}
        />

        <SyncStatusCard
          title={COPY.pullCardTitle}
          status="synced"
          lastSyncTime={syncStatus.last_pulled_at}
          changeCount={lastPullCount}
          isLoading={pullMutation.isPending}
          onAction={handlePull}
        />
      </div>

      <div
        style={{
          padding: "12px 16px",
          backgroundColor: "var(--canvas-bg-2)",
          borderRadius: "var(--radius-md, 6px)",
          fontSize: "12px",
        }}
      >
        <div style={{ color: "var(--canvas-fg-3)", marginBottom: "4px" }}>
          {COPY.syncTargetLabel}
        </div>
        <div
          style={{
            fontFamily: "var(--mono)",
            color: "var(--canvas-fg-2)",
            wordBreak: "break-all",
          }}
        >
          {getSyncTargetUrl()}
        </div>
      </div>
    </div>
  );
}
