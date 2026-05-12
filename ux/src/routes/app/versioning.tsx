import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { Tabs } from "@/components/ui/Tabs";
import { ChangesetPanel } from "@/components/versioning/ChangesetPanel";
import { SyncStatusPanel } from "@/components/versioning/SyncStatus";

export const Route = createFileRoute("/app/versioning")({
  component: VersioningPage,
});

function VersioningPage() {
  const { toast } = useToasts();
  const [activeTab, setActiveTab] = useState("changesets");

  const handleConflictDetected = () => {
    toast("info", "Conflict detected. Navigate to Conflict Resolver tab to resolve.");
  };

  const tabs = [
    { id: "changesets", label: "Changesets" },
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

      {activeTab === "sync" && (
        <div style={{ padding: "20px 0" }}>
          <SyncStatusPanel onConflictDetected={handleConflictDetected} />
        </div>
      )}
    </div>
  );
}
