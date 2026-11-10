import { useState } from "react";
import { Button, Field, FormCallout, InspectorPanel, TextArea } from "@tinkermonkey/heimdall-ui";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import type { components } from "@/api/types";
import { DrTripleEditor } from "./DrTripleEditor";
import { InUseResolver } from "./InUseResolver";
import {
  blockersOf,
  datasetImpactText,
  isDrEditable,
  staleCauseText,
  type StaleCause,
} from "./decisionModel";
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
  // While the reviewer's answers differ from the plan's, every action applies them: the
  // operation never falls back to the plan (or a blocked delete to its delete).
  const picksChanged = !!picks?.changed;
  const sameAsLastEdit =
    !!picks?.fields &&
    JSON.stringify(picks.fields) === JSON.stringify(actions.lastEditOf(operation.id));
  // The server refused the edit these very picks make (invalid_edit / refused): pick
  // other answers, the plan's back, or reject. A failed resolution is not a refused edit.
  const picksRefused = picksChanged && sameAsLastEdit && actions.editRefused(operation);
  // Without picks, after a failed edit the generic button applies the proposal.
  const editFailed = !picksChanged && actions.editFailed(operation);
  const keepsCurrent = picksChanged && !!picks?.keepsCurrent;
  // Answers that make another triple but can't be written as an edit: never a silent accept.
  const unappliable = picksChanged && !picks?.keepsCurrent && !picks?.fields;
  const withPicks = picksChanged && !keepsCurrent && !unappliable && !picksRefused;
  // The relationships using the type: a delete's or retarget's blockers, a rename's usage.
  const usage = blockers ?? operation.type_usage ?? undefined;
  // Picks that retarget a type in use resolve its relationships with the edit; picks that
  // rename or reverse it need no resolution, so a blocked delete then applies as an edit.
  const picksRetarget = withPicks && picks?.pair === "different" && !!usage?.edges.length;
  const resolver = picksChanged ? (picksRetarget ? usage : undefined) : blockers;
  const pickOptions =
    withPicks && picks?.fields && picks.chosenAlternative
      ? {
          edits: { [operation.id]: picks.fields },
          chosenAlternatives: { [operation.id]: picks.chosenAlternative },
        }
      : {};
  const acceptLabel = editFailed
    ? "Apply as proposed"
    : picksChanged
      ? "Accept with my picks"
      : operation.stale
        ? "Apply anyway"
        : failed
          ? "Apply again"
          : operation.reflection
            ? "Accept plan"
            : "Accept";
  const acceptOperation = () => actions.accept([operation.id], pickOptions);

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
        {failed && !operation.stale && !resolver && !picksChanged && (
          <FormCallout variant="error" icon="alert" data-testid="operation-failed-callout">
            {editFailed
              ? "The edit wasn't applied (the reason is under Change). Edit it again, apply the proposal as it stands, or reject it."
              : "The last apply failed (the reason is under Change). Apply it again, or reject it."}
          </FormCallout>
        )}

        {!!operation.dataset_impact?.length && (
          <FormCallout variant="info" icon="info" data-testid="operation-dataset-impact">
            Data that yields to the schema follows this change, without blocking it.
            <ul className="op-decision__impact" aria-label="Data that follows the change">
              {operation.dataset_impact.map((impact) => (
                <li
                  key={impact.dataset_id}
                  data-testid={`operation-dataset-impact-${impact.identifier}`}
                >
                  {datasetImpactText(impact)}
                </li>
              ))}
            </ul>
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
        {picksRefused && picks && (
          <FormCallout variant="error" icon="alert" data-testid="operation-picks-callout">
            The edit your picks make ({picks.triple}) was refused: the reason is under Change. Pick
            other answers, the plan&apos;s answers back, or reject the operation.
          </FormCallout>
        )}
        {unappliable && picks && (
          <FormCallout variant="warn" icon="alert" data-testid="operation-picks-callout">
            Your picks make {picks.triple}, but this proposal recorded no class ids to apply it
            with. Pick the plan&apos;s answers back, or reject the operation.
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
            {resolver && (
              <InUseResolver
                key={picksRetarget ? "retarget-edit" : "as-proposed"}
                operation={operation}
                blockers={resolver}
                busy={actions.busy}
                lastResolution={actions.lastResolutionOf(operation.id)}
                failureReason={resolutionFailure(
                  operation,
                  !!actions.lastResolutionOf(operation.id),
                )}
                retargetEdit={picksRetarget ? picks?.triple : undefined}
                onApply={(resolution) =>
                  actions.accept([operation.id], {
                    ...pickOptions,
                    resolutions: { [operation.id]: resolution },
                  })
                }
              />
            )}
            <div className="op-decision__actions" role="group" aria-label="Decision">
              {!resolver && (
                <Button
                  variant="primary"
                  size="sm"
                  disabled={actions.busy || (picksChanged && !withPicks)}
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
