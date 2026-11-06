import { Chip, InspectorPanel } from "@tinkermonkey/heimdall-ui";
import type { DrDecision, ProposedOperation } from "@/api/services/proposals";
import { decidedByLabel, decidedRecord, decisionState } from "./decisionModel";
import "./proposals.css";

interface OperationDecidedProps {
  operation: ProposedOperation;
  /** Its recorded decision (who and when), once loaded. */
  decision?: DrDecision;
  /** False once the proposal is reverted: nothing it applied stands to undo. */
  revertible: boolean;
}

/**
 * The inspector's Decision section for a decided operation: its state, who
 * decided it and when, what the decision did, and that nothing is left to decide.
 */
export function OperationDecided({ operation, decision, revertible }: OperationDecidedProps) {
  const state = decisionState(operation);
  const who = decidedByLabel(decision?.decided_by, decision?.decided_at);
  const record = decidedRecord(operation);
  const undo = revertible && operation.status === "applied";
  return (
    <InspectorPanel.Section title="Decision">
      <div
        className="op-inspector__stack op-decided"
        data-testid="operation-decided"
        data-state={state.state}
      >
        <div className="op-inspector__status">
          <Chip variant={state.variant} data-testid="operation-decided-state">
            {state.label}
          </Chip>
          {who && (
            <span className="op-decided__who" data-testid="operation-decided-by">
              {who}
            </span>
          )}
        </div>
        {record && (
          <p className="op-decided__note" data-testid="operation-decided-record">
            {record}
          </p>
        )}
        <p className="op-decided__note">
          Nothing left to decide.{undo ? " Revert the proposal to undo it." : ""}
        </p>
      </div>
    </InspectorPanel.Section>
  );
}
