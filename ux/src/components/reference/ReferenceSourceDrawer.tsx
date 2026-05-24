import { Drawer } from "@/components/ui/Drawer";
import { Button, Chip } from "@tinkermonkey/heimdall-ui";
import { useToasts } from "@/components/ui/Toast";
import { useReferenceStatus } from "@/api/hooks/reference";
import type { components } from "@/api/types";

type ReferenceSourceStatusSchema = components["schemas"]["ReferenceSourceStatusSchema"];

interface ReferenceSourceDrawerProps {
  source: ReferenceSourceStatusSchema;
  onClose: () => void;
}

export function ReferenceSourceDrawer({ source, onClose }: ReferenceSourceDrawerProps) {
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
    <Drawer open title={source.name} onClose={onClose}>
      <div className="kv" data-testid="reference-source-drawer">
        <div className="kv-row">
          <div className="kv-label">Status</div>
          <div className="kv-value">
            <Chip variant={source.available ? "emerald" : "neutral"}>{statusLabel}</Chip>
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
              onClick={handleRefresh}
              data-testid={`reference-source-refresh-${source.name}`}
            >
              Refresh
            </Button>
          </div>
        </div>
      </div>
    </Drawer>
  );
}
