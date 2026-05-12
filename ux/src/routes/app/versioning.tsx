import { useState } from "react";
import { createFileRoute, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Tabs } from "@/components/ui/Tabs";
import { ChangesetPanel } from "@/components/versioning/ChangesetPanel";
import { SyncStatusPanel } from "@/components/versioning/SyncStatus";
import { ConflictResolver } from "@/components/versioning/ConflictResolver";
import { EmptyState } from "@/components/ui/EmptyState";

export const Route = createFileRoute("/app/versioning")({
  component: VersioningPage,
  validateSearch: (search) => ({
    proposalId: (search as Record<string, unknown>)?.proposalId as string | undefined,
  }),
});

function VersioningPage() {
  const { toast } = useToasts();
  const search = useSearch({ from: "/app/versioning" });
  const [activeTab, setActiveTab] = useState("changesets");

  const handleConflictDetected = () => {
    setActiveTab("conflicts");
    toast("info", "Conflict detected. Resolve conflicts to proceed.");
  };

  const tabs = [
    { id: "changesets", label: "Changesets" },
    { id: "conflicts", label: "Conflicts" },
    { id: "sync", label: "Sync Status" },
  ];

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>Versioning</h1>
          <p className="subtitle">Manage changesets and synchronization</p>
        </div>
      </div>

      <Tabs tabs={tabs} active={activeTab} onChange={setActiveTab} />

      {activeTab === "changesets" && (
        <ChangesetPanel
          onError={(message: string) => toast("error", message)}
          onConflictDetected={handleConflictDetected}
        />
      )}

      {activeTab === "conflicts" && (
        <div style={{ padding: "20px 0" }}>
          {search.proposalId ? (
            <ConflictResolver
              proposalId={search.proposalId}
              onResolved={() => {
                toast("success", "Conflicts resolved successfully!");
                setActiveTab("changesets");
              }}
            />
          ) : (
            <EmptyState
              title="No proposal selected"
              description="Select a proposal with conflicts to resolve"
            />
          )}
        </div>
      )}

      {activeTab === "sync" && (
        <div style={{ padding: "20px 0" }}>
          <SyncStatusPanel onConflictDetected={handleConflictDetected} />
        </div>
      )}
    </div>
  );
}
