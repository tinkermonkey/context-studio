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
      <div className="error-banner-compact" data-testid="error-banner-compact">
        <AlertCircle size={16} className="error-banner-icon" />
        <span className="error-banner-message compact">{message}</span>
        <div className="error-banner-actions compact">
          <button
            type="button"
            onClick={handleCopyLogPath}
            title="Copy daemon log path"
            className="error-banner-btn compact"
            data-testid="error-banner-logs-btn"
          >
            <FileText size={12} />
            Logs
          </button>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              title="Retry loading"
              className="error-banner-btn compact"
              data-testid="error-banner-retry-btn"
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
    <div className="error-banner" data-testid="error-banner">
      <AlertCircle size={18} className="error-banner-icon" />
      <div className="error-banner-content">
        <div className="error-banner-message">{message}</div>
        {error.message && <div className="error-banner-error-text">{error.message}</div>}
      </div>
      <div className="error-banner-actions">
        <button
          type="button"
          onClick={handleCopyLogPath}
          title="Copy daemon log path"
          className="error-banner-btn"
          data-testid="error-banner-logs-btn"
        >
          <FileText size={14} />
          Logs
        </button>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            title="Retry loading"
            className="error-banner-btn error-banner-btn-primary"
            data-testid="error-banner-retry-btn"
          >
            <RefreshCw size={14} />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
