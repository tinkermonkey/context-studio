import { useState } from "react";
import { Button, Field, FormCallout, InspectorPanel, TextArea } from "@tinkermonkey/heimdall-ui";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import type { components } from "@/api/types";
import { DrTripleEditor } from "./DrTripleEditor";
import { InUseResolver } from "./InUseResolver";
import { blockersOf, isDrEditable, staleCauseText, type StaleCause } from "./decisionModel";
import type { TripleSource } from "./proposalModel";
import type { PickOutcome } from "./tieredModel";
import type { ProposalActions } from "./useProposalActions";
import "./proposals.css";

type Taxonomy = components["schemas"]["TaxonomyResponse"];

interface OperationDecisionProps {
  operation: ProposedOperation;
  proposal: ChangeProposal;
  taxonomy?: Taxonomy;
  /** The target property definition as it stands now, once loaded. */
  current?: TripleSource;
  staleCause?: StaleCause;
  actions: ProposalActions;
  /** A reflection operation: what the reviewer's answer picks make of it. */
  picks?: PickOutcome;
}

/**
 * The inspector's Decision section for an operation awaiting a decision:
 * Accept (Apply anyway when stale, Apply again when failed), "Edit, then
 * accept" or "Replace instead" for a DR relationship type, and Reject with an
 * optional reason. A relationship-type delete that relationships still use
 * resolves them instead of Accept (move them or delete them too), and its
 * Reject keeps the type.
 */
/** The plain in-use failure of a delete applied without a resolution. */
const IN_USE_FAILURE = /is in use by \d+ relationship/;

/**
 * Why a blocked delete's last resolution failed, if it did. The plain in-use
 * failure (applied without a resolution) only repeats the Blocked callout.
 */
function resolutionFailure(operation: ProposedOperation, resolutionSent: boolean) {
  if (operation.status !== "failed" || !operation.reason) return undefined;
  if (!resolutionSent && IN_USE_FAILURE.test(operation.reason)) return undefined;
  return operation.reason;
}

export function OperationDecision({
  operation,
  proposal,
  taxonomy,
  current,
  staleCause,
  actions,
  picks,
}: OperationDecisionProps) {
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const editable = !!taxonomy && isDrEditable(operation, taxonomy.identifier);
  const failed = operation.status === "failed";
  const blockers = blockersOf(operation);
  const noteId = `operation-reject-note-${operation.id}`;
  // After a failed edit the generic button applies the proposal, not the edit.
  const editFailed = actions.editFailed(operation);
  // Answers other than the plan's apply as an edit, unless a failed edit is applied as proposed.
  const withPicks = !editFailed && !!picks?.changed && !!picks.fields;
  const keepsCurrent = !editFailed && !!picks?.keepsCurrent;
  const acceptLabel = editFailed
    ? "Apply as proposed"
    : withPicks
      ? "Accept with my picks"
      : operation.stale
        ? "Apply anyway"
        : failed
          ? "Apply again"
          : operation.reflection
            ? "Accept plan"
            : "Accept";
  const acceptOperation = () =>
    withPicks && picks?.fields && picks.chosenAlternative
      ? actions.accept([operation.id], {
          edits: { [operation.id]: picks.fields },
          chosenAlternatives: { [operation.id]: picks.chosenAlternative },
        })
      : actions.accept([operation.id]);

  return (
    <InspectorPanel.Section title="Decision">
      <div className="op-inspector__stack op-decision" data-testid="operation-decision">
        {operation.stale && (
          <FormCallout variant="warn" icon="alert" data-testid="operation-stale-callout">
            {staleCause?.gone
              ? `${staleCauseText(staleCause)} Reject it, unless the target comes back.`
              : `${staleCause ? staleCauseText(staleCause) : "Its target changed after it was proposed."} Applying it needs Apply anyway, which keeps the proposed values.`}
          </FormCallout>
        )}
        {failed && !operation.stale && !blockers && (
          <FormCallout variant="error" icon="alert" data-testid="operation-failed-callout">
            {editFailed
              ? "The edit wasn't applied (the reason is under Change). Edit it again, apply the proposal as it stands, or reject it."
              : "The last apply failed (the reason is under Change). Apply it again, or reject it."}
          </FormCallout>
        )}

        {withPicks && picks && (
          <FormCallout variant="info" icon="info" data-testid="operation-picks-callout">
            Your picks make {picks.triple} instead of the plan&apos;s {picks.planTriple}. It applies
            as an edit, and gold records the alternative you chose.
          </FormCallout>
        )}
        {keepsCurrent && picks && (
          <FormCallout variant="warn" icon="alert" data-testid="operation-picks-callout">
            Your picks keep the current triple {picks.triple}. To keep it, reject the operation.
          </FormCallout>
        )}
        {editing && taxonomy ? (
          <DrTripleEditor
            operation={operation}
            proposal={proposal}
            taxonomy={taxonomy}
            current={current}
            lastEdit={actions.lastEditOf(operation.id)}
            busy={actions.busy}
            onApply={(edits) => actions.accept([operation.id], { edits })}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            {blockers && (
              <InUseResolver
                operation={operation}
                blockers={blockers}
                busy={actions.busy}
                lastResolution={actions.lastResolutionOf(operation.id)}
                failureReason={resolutionFailure(
                  operation,
                  !!actions.lastResolutionOf(operation.id),
                )}
                onApply={(resolution) =>
                  actions.accept([operation.id], {
                    resolutions: { [operation.id]: resolution },
                  })
                }
              />
            )}
            <div className="op-decision__actions" role="group" aria-label="Decision">
              {!blockers && (
                <Button
                  variant="primary"
                  size="sm"
                  disabled={actions.busy || keepsCurrent}
                  onClick={acceptOperation}
                  data-testid="operation-accept"
                >
                  {acceptLabel}
                </Button>
              )}
              {editable && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={actions.busy}
                  onClick={() => setEditing(true)}
                  data-testid="operation-edit"
                >
                  {operation.op === "delete" ? "Replace instead" : "Edit, then accept"}
                </Button>
              )}
              <Button
                variant="danger"
                size="sm"
                disabled={actions.busy}
                onClick={() => actions.rejectOperations([operation.id], note)}
                data-testid="operation-reject"
              >
                {blockers ? "Keep the type (reject)" : "Reject"}
              </Button>
            </div>
            <Field label="Reason" hint="optional, stored with a reject" htmlFor={noteId}>
              <TextArea
                id={noteId}
                rows={2}
                value={note}
                placeholder={blockers ? "Why keep the type?" : "Why reject it?"}
                onChange={(e) => setNote(e.target.value)}
                data-testid="operation-reject-note"
              />
            </Field>
          </>
        )}
      </div>
    </InspectorPanel.Section>
  );
}
