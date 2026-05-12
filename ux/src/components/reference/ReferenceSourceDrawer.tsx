import { Button } from "@/components/ui/Button";
import { useToasts } from "@/components/ui/Toast";
import { useReferenceStatus } from "@/api/hooks/reference";
import type { components } from "@/api/types";

type ReferenceSourceStatusSchema = components["schemas"]["ReferenceSourceStatusSchema"];

interface ReferenceSourceDrawerProps {
  source: ReferenceSourceStatusSchema;
  onClose: () => void;
}

export function ReferenceSourceDrawer({
  source,
  onClose,
}: ReferenceSourceDrawerProps) {
  const { refetch } = useReferenceStatus();
  const { toast } = useToasts();

  const handleRefresh = async () => {
    try {
      await refetch();
      toast("success", `Refreshed ${source.name}`);
    } catch (error) {
      toast("error", `Failed to refresh ${source.name}`);
    }
  };

  const lastCheckedDate = source.last_checked
    ? new Date(source.last_checked).toLocaleString()
    : "—";

  const statusLabel = source.available ? "Active" : "Inactive";
  const statusBgColor = source.available
    ? "var(--emerald-100, #d1fae5)"
    : "var(--gray-100, #f3f4f6)";
  const statusTextColor = source.available
    ? "var(--emerald-800, #065f46)"
    : "var(--gray-600, #4b5563)";

  return (
    <div className="kv">
      <div className="kv-row">
        <div className="kv-label">Source</div>
        <div className="kv-value">{source.name}</div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Status</div>
        <div className="kv-value">
          <span
            style={{
              backgroundColor: statusBgColor,
              color: statusTextColor,
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "var(--text-xs)",
              fontWeight: 500,
            }}
          >
            {statusLabel}
          </span>
        </div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Last Checked</div>
        <div className="kv-value muted-text">{lastCheckedDate}</div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Actions</div>
        <div className="kv-value">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            data-testid={`reference-source-refresh-${source.name}`}
          >
            Refresh
          </Button>
        </div>
      </div>
    </div>
  );
}
