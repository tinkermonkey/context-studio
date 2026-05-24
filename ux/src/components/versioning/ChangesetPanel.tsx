import { useState } from "react";
import { Button } from "@tinkermonkey/heimdall-ui";
import { useChanges, useCreateChangeset } from "@/api/hooks/versioning";
import { useToasts } from "@/components/ui/Toast";
import { PendingChangesList } from "./PendingChangesList";
import { ChangesetListSection } from "./ChangesetListSection";
import { CreateChangesetModal } from "./CreateChangesetModal";
import { COPY } from "@/routes/app/versioning/copy";

interface ChangesetPanelProps {
  onError?: (message: string) => void;
  onConflictDetected?: () => void;
}

export function ChangesetPanel({ onError, onConflictDetected }: ChangesetPanelProps) {
  const { toast } = useToasts();
  const [selectedChanges, setSelectedChanges] = useState<Set<string>>(new Set());
  const [showCreateModal, setShowCreateModal] = useState(false);

  const {
    data: changesData,
    isLoading: changesLoading,
    error: changesError,
    refetch: refetchChanges,
  } = useChanges();

  const createChangesetMutation = useCreateChangeset();

  const handleCreateChangeset = async (name: string, description?: string) => {
    try {
      const selectedIds = Array.from(selectedChanges);
      await createChangesetMutation.mutateAsync({
        name,
        description,
        event_ids: selectedIds,
      });
      setSelectedChanges(new Set());
      setShowCreateModal(false);
      toast("success", COPY.changesetCreatedSuccess);
    } catch (error) {
      const message = error instanceof Error ? error.message : COPY.failedToCreateChangeset;
      if (onError) {
        onError(message);
      } else {
        toast("error", message);
      }
    }
  };

  const handleSelectChange = (changeId: string, selected: boolean) => {
    const newSet = new Set(selectedChanges);
    if (selected) {
      newSet.add(changeId);
    } else {
      newSet.delete(changeId);
    }
    setSelectedChanges(newSet);
  };

  const handleSelectAllChanges = (selected: boolean) => {
    if (selected && changesData?.events) {
      const allIds = changesData.events.map((e) => e.id);
      setSelectedChanges(new Set(allIds));
    } else {
      setSelectedChanges(new Set());
    }
  };

  const handleStageSelected = () => {
    if (selectedChanges.size === 0) {
      toast("error", COPY.selectAtLeastOneChange);
      return;
    }
    setShowCreateModal(true);
  };

  return (
    <>
      <div
        data-testid="changeset-panel"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "20px",
          minHeight: "calc(100vh - 180px)",
        }}
      >
        {/* Left Column - Pending Changes */}
        <div className="col" style={{ gap: "12px", overflow: "hidden" }}>
          <div className="between">
            <h2 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>
              {COPY.pendingChangesHeading}
            </h2>
            <Button
              onClick={handleStageSelected}
              disabled={selectedChanges.size === 0 || createChangesetMutation.isPending}
              variant="primary"
            >
              {COPY.stageSelectedButton}
            </Button>
          </div>

          <PendingChangesList
            changes={changesData?.events || []}
            selectedIds={selectedChanges}
            isLoading={changesLoading}
            error={changesError}
            onSelectChange={handleSelectChange}
            onSelectAll={handleSelectAllChanges}
            onRetry={refetchChanges}
          />
        </div>

        {/* Right Column - Changesets */}
        <div className="col" style={{ gap: "12px", overflow: "hidden" }}>
          <div>
            <h2 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>
              {COPY.changesetListHeading}
            </h2>
          </div>

          <ChangesetListSection onApplyError={onError} onConflictDetected={onConflictDetected} />
        </div>
      </div>

      {/* Create Changeset Modal */}
      <CreateChangesetModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={handleCreateChangeset}
        isLoading={createChangesetMutation.isPending}
        selectedCount={selectedChanges.size}
      />
    </>
  );
}
