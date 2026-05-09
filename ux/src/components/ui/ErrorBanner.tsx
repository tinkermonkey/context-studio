import { RefreshCw, AlertCircle } from "lucide-react";

interface ErrorBannerProps {
  error: Error | null;
  onRetry: () => void;
  message?: string;
  compact?: boolean;
}

export function ErrorBanner({
  error,
  onRetry,
  message = "Failed to load data",
  compact = false,
}: ErrorBannerProps) {
  if (!error) return null;

  if (compact) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 12px",
          borderRadius: "var(--radius-md, 6px)",
          background: "var(--rose-50, #fff7f5)",
          border: "1px solid var(--rose-200, #fecaca)",
        }}
      >
        <AlertCircle size={16} style={{ color: "var(--rose-600, #e11d48)" }} />
        <span style={{ flex: 1, fontSize: "var(--text-xs)", color: "var(--rose-700, #be123c)" }}>
          {message}
        </span>
        <button
          type="button"
          onClick={onRetry}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: "4px 8px",
            borderRadius: "4px",
            background: "transparent",
            border: "1px solid var(--rose-300, #fda4af)",
            color: "var(--rose-700, #be123c)",
            fontSize: "var(--text-xs)",
            cursor: "pointer",
            transition: "background 0.15s",
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "var(--rose-100, #ffe4e6)";
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.background = "transparent";
          }}
        >
          <RefreshCw size={12} />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-3, 12px)",
        padding: "var(--space-4, 16px)",
        borderRadius: "var(--radius-md, 6px)",
        background: "var(--rose-50, #fff7f5)",
        border: "1px solid var(--rose-200, #fecaca)",
      }}
    >
      <AlertCircle size={18} style={{ color: "var(--rose-600, #e11d48)", flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div
          style={{
            fontSize: "var(--text-sm)",
            fontWeight: 500,
            color: "var(--rose-900, #4c0519)",
            marginBottom: 4,
          }}
        >
          {message}
        </div>
        {error.message && (
          <div
            style={{
              fontSize: "var(--text-xs)",
              color: "var(--rose-700, #be123c)",
              fontFamily: "var(--mono)",
            }}
          >
            {error.message}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={onRetry}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 16px",
          borderRadius: "var(--radius-md, 6px)",
          background: "var(--rose-600, #e11d48)",
          border: "1px solid var(--rose-700, #be123c)",
          color: "white",
          fontSize: "var(--text-sm)",
          fontWeight: 500,
          cursor: "pointer",
          transition: "background 0.15s",
          flexShrink: 0,
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "var(--rose-700, #be123c)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.background = "var(--rose-600, #e11d48)";
        }}
      >
        <RefreshCw size={14} />
        Retry
      </button>
    </div>
  );
}
