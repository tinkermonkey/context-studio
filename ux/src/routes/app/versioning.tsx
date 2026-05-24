import { useState } from "react";
import { createFileRoute, useSearch } from "@tanstack/react-router";
import { useToasts } from "@/components/ui/Toast";
import { TabBar, PageHeader } from "@tinkermonkey/heimdall-ui";
import { ChangesetPanel } from "@/components/versioning/ChangesetPanel";
import { SyncStatusPanel } from "@/components/versioning/SyncStatus";
import { ConflictResolver } from "@/components/versioning/ConflictResolver";
import { EmptyState } from "@/components/ui/EmptyState";
import { COPY } from "./versioning/copy";

export const Route = createFileRoute("/app/versioning")({
  component: VersioningPage,
  validateSearch: (search) => ({
    proposalId: (search as Record<string, unknown>)?.proposalId as string | undefined,
  }),
});

export function VersioningPage() {
  const { toast } = useToasts();
  const search = useSearch({ from: "/app/versioning" });
  const [activeTab, setActiveTab] = useState("changesets");

  const handleConflictDetected = () => {
    setActiveTab("conflicts");
    toast("info", COPY.conflictDetectedNotification);
  };

  const tabs = [
    { id: "changesets", label: COPY.changesetsTab },
    { id: "conflicts", label: COPY.conflictsTab },
    { id: "sync", label: COPY.syncStatusTab },
  ];

  return (
    <div data-testid="versioning-page">
      <PageHeader
        eyebrow="Collaboration"
        title={COPY.versioningPageTitle}
        subtitle={COPY.versioningPageSubtitle}
      />

      <TabBar tabs={tabs} activeTabId={activeTab} onSelectTab={setActiveTab} />

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
                toast("success", COPY.conflictsResolvedSuccess);
                setActiveTab("changesets");
              }}
            />
          ) : (
            <EmptyState title={COPY.noProposalSelected} description={COPY.selectProposalMessage} />
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
