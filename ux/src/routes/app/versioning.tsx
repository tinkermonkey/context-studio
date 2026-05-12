import { createFileRoute } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { ChangesetPanel } from "@/components/versioning/ChangesetPanel";

export const Route = createFileRoute("/app/versioning")({
  component: VersioningPage,
});

function VersioningPage() {
  const { toast } = useToasts();

  const handleConflictDetected = () => {
    toast("info", "Conflict detected. Navigate to Conflict Resolver tab to resolve.");
  };

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Versioning</h1>
          <p className="subtitle">Manage changesets and synchronization</p>
        </div>
      </div>

      <ChangesetPanel
        onError={(message: string) => toast("error", message)}
        onConflictDetected={handleConflictDetected}
      />
    </div>
  );
}
