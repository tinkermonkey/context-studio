import { RefreshCw, AlertCircle, FileText } from "lucide-react";
import { useToasts } from "./Toast";

interface ErrorBannerProps {
  error: Error | null;
  onRetry?: () => void;
  message?: string;
  compact?: boolean;
  daemonLogPath?: string;
}

export function ErrorBanner({
  error,
  onRetry,
  message = "Failed to load data",
  compact = false,
  daemonLogPath = "/local-server/logs/context_studio.log",
}: ErrorBannerProps) {
  const { toast } = useToasts();

  if (!error) return null;

  const handleCopyLogPath = async () => {
    try {
      await navigator.clipboard.writeText(daemonLogPath);
      toast("success", "Log path copied to clipboard");
    } catch {
      toast("error", "Failed to copy log path");
    }
  };

  if (compact) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 12px",
          borderRadius: "var(--radius-md)",
          background: "rgb(var(--semantic-rose-bg))",
          border: "1px solid rgb(var(--semantic-rose-border))",
        }}
      >
        <AlertCircle size={16} style={{ color: "rgb(var(--status-rose))" }} />
        <span
          style={{ flex: 1, fontSize: "var(--text-xs)", color: "rgb(var(--status-rose-deep))" }}
        >
          {message}
        </span>
        <div style={{ display: "flex", gap: "4px" }}>
          <button
            type="button"
            onClick={handleCopyLogPath}
            title="Copy daemon log path"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              padding: "4px 8px",
              borderRadius: "var(--radius-sm)",
              background: "transparent",
              border: "1px solid rgb(var(--semantic-rose-border))",
              color: "rgb(var(--status-rose-deep))",
              fontSize: "var(--text-xs)",
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "rgb(var(--semantic-rose-bg))";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "transparent";
            }}
          >
            <FileText size={12} />
            Logs
          </button>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              title="Retry loading"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: "4px 8px",
                borderRadius: "var(--radius-sm)",
                background: "transparent",
                border: "1px solid rgb(var(--semantic-rose-border))",
                color: "rgb(var(--status-rose-deep))",
                fontSize: "var(--text-xs)",
                cursor: "pointer",
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background =
                  "rgb(var(--semantic-rose-bg))";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.background = "transparent";
              }}
            >
              <RefreshCw size={12} />
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3)",
        padding: "var(--space-4)",
        borderRadius: "var(--radius-md)",
        background: "rgb(var(--semantic-rose-bg))",
        border: "1px solid rgb(var(--semantic-rose-border))",
      }}
    >
      <AlertCircle size={18} style={{ color: "rgb(var(--status-rose))", flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: "var(--text-sm)",
            fontWeight: 500,
            color: "rgb(var(--status-rose-deep))",
            marginBottom: 4,
          }}
        >
          {message}
        </div>
        {error.message && (
          <div
            style={{
              fontSize: "var(--text-xs)",
              color: "rgb(var(--status-rose-deep))",
              fontFamily: "var(--font-mono)",
            }}
          >
            {error.message}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: "var(--space-2)", flexShrink: 0 }}>
        <button
          type="button"
          onClick={handleCopyLogPath}
          title="Copy daemon log path"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 16px",
            borderRadius: "var(--radius-md)",
            background: "rgb(var(--semantic-rose-bg))",
            border: "1px solid rgb(var(--semantic-rose-border))",
            color: "rgb(var(--status-rose-deep))",
            fontSize: "var(--text-sm)",
            fontWeight: 500,
            cursor: "pointer",
            transition: "background 0.15s",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              "rgb(var(--semantic-rose-border))";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background =
              "rgb(var(--semantic-rose-bg))";
          }}
        >
          <FileText size={14} />
          Logs
        </button>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            title="Retry loading"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 16px",
              borderRadius: "var(--radius-md)",
              background: "rgb(var(--status-rose))",
              border: "1px solid rgb(var(--status-rose-deep))",
              color: "white",
              fontSize: "var(--text-sm)",
              fontWeight: 500,
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "rgb(var(--status-rose-deep))";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background = "rgb(var(--status-rose))";
            }}
          >
            <RefreshCw size={14} />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
