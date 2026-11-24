import { ConfirmDialog } from "@tinkermonkey/heimdall-ui";
import { useRevertPreview } from "@/api/hooks/proposals";
import type { RevertPreviewItem } from "@/api/services/proposals";

const MAX_VALUE_CHARS = 80;

/** A field's value as one short line: strings as they are, anything else as JSON. */
export function previewValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "(empty)";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > MAX_VALUE_CHARS ? `${text.slice(0, MAX_VALUE_CHARS)}…` : text;
}

function PreviewRow({ edit }: { edit: RevertPreviewItem }) {
  return (
    <li
      className="revert-preview__row"
      data-testid={`revert-preview-row-${edit.entity_id}-${edit.field}`}
    >
      <span className="revert-preview__what">
        {edit.label} <span className="revert-preview__field">{edit.field}</span>
      </span>
      <span className="revert-preview__values">
        <span className="revert-preview__now" title={String(edit.current_value ?? "")}>
          now {previewValue(edit.current_value)}
        </span>
        <span className="revert-preview__applied" title={String(edit.applied_value ?? "")}>
          applied as {previewValue(edit.applied_value)}
        </span>
      </span>
    </li>
  );
}

/** What a revert would overwrite: the edits made since the proposal applied it. */
function RevertPreview({ proposalId }: { proposalId: string }) {
  const { data, isPending, isError } = useRevertPreview(proposalId, true);
  if (isPending) {
    return (
      <p className="revert-preview__note" data-testid="revert-preview-loading">
        Checking for edits made since it was applied…
      </p>
    );
  }
  if (isError) {
    return (
      <p
        className="revert-preview__note revert-preview__note--warn"
        role="alert"
        data-testid="revert-preview-error"
      >
        Couldn&apos;t check for edits made since it was applied.
      </p>
    );
  }
  const overwritten = data.overwritten ?? [];
  if (overwritten.length === 0) {
    return (
      <p className="revert-preview__note" data-testid="revert-preview-none">
        No field this proposal updated has been edited since it was applied.
      </p>
    );
  }
  const count = overwritten.length;
  return (
    <div className="revert-preview" role="group" data-testid="revert-preview">
      <p className="revert-preview__note revert-preview__note--warn">
        Reverting overwrites {count} edit{count === 1 ? "" : "s"} made since it was applied:
      </p>
      <ul className="revert-preview__list">
        {overwritten.map((edit) => (
          <PreviewRow key={`${edit.entity_id}:${edit.field}`} edit={edit} />
        ))}
      </ul>
    </div>
  );
}

interface RevertProposalDialogProps {
  proposalId: string;
  isOpen: boolean;
  /** What the revert undoes, in a sentence. */
  summary: string;
  onClose: () => void;
  onConfirm: () => void;
}

/** Confirm an in-place revert, after showing the later edits it would overwrite. */
export function RevertProposalDialog({
  proposalId,
  isOpen,
  summary,
  onClose,
  onConfirm,
}: RevertProposalDialogProps) {
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Revert this proposal?"
      message={
        <div className="stack" data-testid="revert-proposal-dialog">
          <span data-testid="proposal-revert-message">{summary}</span>
          {isOpen && <RevertPreview proposalId={proposalId} />}
        </div>
      }
      confirmLabel="Revert proposal"
    />
  );
}
