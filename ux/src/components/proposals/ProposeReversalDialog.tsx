import { ConfirmDialog } from "@tinkermonkey/heimdall-ui";

interface ProposeReversalDialogProps {
  isOpen: boolean;
  /** How many changes the proposal applied: what the reversal undoes. */
  applied: number;
  onClose: () => void;
  onConfirm: () => void;
}

/**
 * Confirm proposing the reversal of a landed proposal (#1668): why it can't be
 * undone here, what the new proposal holds, and that it is decided like any.
 */
export function ProposeReversalDialog({
  isOpen,
  applied,
  onClose,
  onConfirm,
}: ProposeReversalDialogProps) {
  const changes = `${applied} change${applied === 1 ? "" : "s"}`;
  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title="Propose the reversal?"
      variant="primary"
      message={
        <div className="stack" data-testid="propose-reversal-dialog">
          <p>
            This proposal has landed in its client&apos;s source, so it can&apos;t be undone here:
            the source would bring its changes back.
          </p>
          <p data-testid="propose-reversal-contents">
            A new proposal will undo the {changes} it applied: what it created is deleted, what it
            updated or moved is set back, and what it deleted is restored.
          </p>
          <p>
            The reversal is reviewed, applied and landed like any proposal. Once it lands, this one
            is reversed.
          </p>
        </div>
      }
      confirmLabel="Propose the reversal"
    />
  );
}
