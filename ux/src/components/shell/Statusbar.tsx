import { Network, CheckCircle, AlertCircle } from "lucide-react";
import { useHealth } from "@/api/hooks/admin";
import { usePipelines } from "@/api/hooks/pipeline";
import { useExecutionStore } from "@/stores/executionStore";

export function Statusbar() {
  const { data: health, isError } = useHealth();
  const { inFlightPipelineIds } = useExecutionStore();
  const runningCount = inFlightPipelineIds.size;
  const hasRunning = runningCount > 0;

  usePipelines(hasRunning ? 5000 : false);

  const isHealthy = !isError && health?.status === "healthy";
  const isDegraded = !isError && health?.status === "degraded";
  const statusLabel = isError ? "api offline" : health ? health.status : "connecting...";

  const uptimeLabel = health ? `up ${Math.floor(health.uptime_seconds / 60)}m` : null;

  return (
    <div className="statusbar">
      <div className="statusbar-group">
        <span className="sb-item">
          <span
            className="status-pulse"
            style={{
              background: isError
                ? "var(--rose-500, #f43f5e)"
                : isDegraded
                  ? "var(--amber-400, #fbbf24)"
                  : isHealthy
                    ? undefined
                    : "var(--canvas-fg-3)",
            }}
          />
          <span>api server</span>
          <span className="sb-mono">:8100</span>
          <span className="sb-mono" style={{ marginLeft: 4 }}>
            {statusLabel}
          </span>
        </span>
        <span className="sb-divider" />
        <span className="sb-item">
          {isError ? <AlertCircle size={11} /> : <Network size={11} />}
          <span>
            {isError
              ? "cannot reach api"
              : health?.database_connected
                ? "database connected"
                : "database unavailable"}
          </span>
        </span>
      </div>
      <div className="statusbar-group">
        {hasRunning && (
          <>
            <span className="sb-item">
              <span className="status-pulse running" />
              <span className="sb-mono">
                {runningCount} pipeline{runningCount > 1 ? "s" : ""} running
              </span>
            </span>
            <span className="sb-divider" />
          </>
        )}
        {uptimeLabel && (
          <>
            <span className="sb-item">
              <span className="sb-mono">{uptimeLabel}</span>
            </span>
            <span className="sb-divider" />
          </>
        )}
        <span className="sb-item">
          <span className="sb-mono">UTF-8 · LF</span>
        </span>
        <span className="sb-divider" />
        <span className="sb-item">
          <CheckCircle size={11} />
          <span className="sb-mono">local</span>
        </span>
      </div>
    </div>
  );
}
