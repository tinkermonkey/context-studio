import { useState } from "react";
import { Modal } from "@/components/ui/Modal";
import { Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { usePublishTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
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

  const handlePublish = async () => {
    try {
      await publishMutation.mutateAsync({
        id: taxonomy.id,
        commitMessage,
      });
      setCommitMessage("");
      onPublish?.();
      onClose();
    } catch {
      // Error is handled by the mutation error state
    }
  };

  const canPublish = commitMessage.trim().length > 0 && !publishMutation.isPending;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Publish Taxonomy"
      size="sm"
      data-testid="taxonomy-publish-dialog"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--canvas-fg-2)", marginBottom: "var(--space-2)" }}>
            Publishing will transition this taxonomy from draft to published status.
          </p>
        </div>

        {/* TODO: Add diff summary display when backend provides changeset/diff endpoint */}
        <div style={{ padding: "var(--space-2)", backgroundColor: "var(--canvas-fg-4)", borderRadius: "4px", fontSize: "var(--text-xs)", color: "var(--canvas-fg-3)" }}>
          Diff summary coming soon…
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
