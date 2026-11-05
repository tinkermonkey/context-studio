import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { TabBar, PageHeader } from "@tinkermonkey/heimdall-ui";
import { ChangeHistoryList } from "@/components/versioning/ChangeHistoryList";
import { SyncStatusPanel } from "@/components/versioning/SyncStatus";
import { COPY } from "./versioning/copy";

export const Route = createFileRoute("/app/versioning")({
  component: VersioningPage,
});

export function VersioningPage() {
  const [activeTab, setActiveTab] = useState("changes");

  const tabs = [
    { id: "changes", label: COPY.changesTab },
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

      {activeTab === "changes" && (
        <div style={{ padding: "20px 0" }}>
          <ChangeHistoryList />
        </div>
      )}

      {activeTab === "sync" && (
        <div style={{ padding: "20px 0" }}>
          <SyncStatusPanel />
        </div>
      )}
    </div>
  );
}
