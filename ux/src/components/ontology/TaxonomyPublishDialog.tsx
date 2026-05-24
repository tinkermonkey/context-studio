import { TextArea as Textarea, Button, Modal } from "@tinkermonkey/heimdall-ui";
import { useState } from "react";

import { useToasts } from "@/components/ui/Toast";
import { usePublishTaxonomy, usePublishDiffStats } from "@/api/hooks/ontology/useTaxonomies";
import type { components } from "@/api/types";

type TaxonomyResponse = components["schemas"]["TaxonomyResponse"];

interface TaxonomyPublishDialogProps {
  open: boolean;
  onClose: () => void;
  taxonomy: TaxonomyResponse;
  onPublish?: () => void;
}

export function TaxonomyPublishDialog({
  open,
  onClose,
  taxonomy,
  onPublish,
}: TaxonomyPublishDialogProps) {
  const [commitMessage, setCommitMessage] = useState("");
  const publishMutation = usePublishTaxonomy();
  const diffStatsQuery = usePublishDiffStats(taxonomy.id);
  const { toast } = useToasts();

  const handlePublish = async () => {
    try {
      await publishMutation.mutateAsync({
        id: taxonomy.id,
        commitMessage,
      });
      setCommitMessage("");
      onPublish?.();
      onClose();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to publish taxonomy";
      toast("error", message);
    }
  };

  const canPublish = commitMessage.trim().length > 0 && !publishMutation.isPending;

  return (
    <Modal isOpen={open}
      onClose={onClose}
      title="Publish Taxonomy"
      data-testid="taxonomy-publish-dialog"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <p
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--canvas-fg-2)",
              marginBottom: "var(--space-2)",
            }}
          >
            Publishing will transition this taxonomy from draft to published status.
          </p>
        </div>

        <div
          style={{
            padding: "var(--space-2)",
            backgroundColor: "rgb(var(--canvas-fg-4))",
            borderRadius: "4px",
            fontSize: "var(--text-xs)",
            color: "var(--canvas-fg-3)",
          }}
        >
          {diffStatsQuery.isLoading ? (
            <span>Loading diff summary…</span>
          ) : diffStatsQuery.data ? (
            <span>
              {(() => {
                const parts = [];
                if (diffStatsQuery.data.added > 0) {
                  parts.push(
                    `${diffStatsQuery.data.added} class${diffStatsQuery.data.added !== 1 ? "es" : ""} added`,
                  );
                }
                if (diffStatsQuery.data.modified > 0) {
                  parts.push(`${diffStatsQuery.data.modified} modified`);
                }
                if (diffStatsQuery.data.removed > 0) {
                  parts.push(`${diffStatsQuery.data.removed} removed`);
                }
                return parts.length > 0 ? parts.join(", ") : "No changes to publish";
              })()}
            </span>
          ) : (
            <span>Unable to load diff summary</span>
          )}
        </div>

        <div>
          <label style={{ display: "block", fontSize: "var(--text-sm)", marginBottom: "4px" }}>
            Publication Message
          </label>
          <Textarea
            placeholder="Describe this publication…"
            value={commitMessage}
            onChange={(e) => setCommitMessage(e.target.value)}
            data-testid="taxonomy-publish-message-input"
            rows={4}
          />
        </div>

        <div style={{ display: "flex", gap: "var(--space-2)", justifyContent: "flex-end" }}>
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={publishMutation.isPending}
            data-testid="taxonomy-publish-cancel-button"
          >
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={handlePublish}
            disabled={!canPublish}
            data-testid="taxonomy-publish-confirm-button"
          >
            {publishMutation.isPending ? "Publishing…" : "Publish"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
