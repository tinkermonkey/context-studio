import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
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
  onClose: _onClose,
}: ReferenceSourceDrawerProps) {
  const { refetch } = useReferenceStatus();
  const { toast } = useToasts();

  const handleRefresh = async () => {
    try {
      await refetch();
      toast("success", `Refreshed ${source.name}`);
    } catch {
      toast("error", `Failed to refresh ${source.name}`);
    }
  };

  const lastCheckedDate = source.last_checked
    ? new Date(source.last_checked).toLocaleString()
    : "—";

  const statusLabel = source.available ? "Active" : "Inactive";

  return (
    <div className="kv" data-testid="reference-source-drawer">
      <div className="kv-row">
        <div className="kv-label">Source</div>
        <div className="kv-value">{source.name}</div>
      </div>

      <div className="kv-row">
        <div className="kv-label">Status</div>
        <div className="kv-value">
          <Chip color={source.available ? "emerald" : "gray"}>
            {statusLabel}
          </Chip>
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
