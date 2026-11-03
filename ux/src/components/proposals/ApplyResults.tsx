import {
  Button,
  Chip,
  FormCallout,
  Panel,
  StatGrid,
  StatTile,
  Table,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import type { ChangeProposal } from "@/api/services/proposals";
import { OperationDiff } from "./OperationDiff";
import { outcomeRows, type OutcomeRow } from "./decisionModel";
import { OPERATION_STATUS_VARIANT, OP_VARIANT, tallyOperations } from "./proposalModel";
import type { OperationContext } from "./useOperationContext";
import type { ProposalActions } from "./useProposalActions";
import "./proposals.css";

/** One table row; the extra keys give each column its own key. */
type Row = OutcomeRow & { id: string; seq: number; op: string; outcome: string };

function seqList(rows: Row[]): string {
  const seqs = rows.map((r) => r.operation.seq);
  return seqs.length === 1 ? `Seq ${seqs[0]}` : `Seqs ${seqs.join(", ")}`;
}

interface ApplyResultsProps {
  proposal: ChangeProposal;
  /** The operations the last apply sent. */
  operationIds: string[];
  context: OperationContext;
  actions: ProposalActions;
}

/**
 * The outcome of the last apply: a warning when some failed (applies aren't
 * atomic), the proposal's tally, and each sent operation's outcome. A failed
 * one can be applied again or rejected from here.
 */
export function ApplyResults({ proposal, operationIds, context, actions }: ApplyResultsProps) {
  const rows: Row[] = outcomeRows(proposal, operationIds).map((r) => ({
    ...r,
    id: r.operation.id,
    seq: r.operation.seq,
    op: r.operation.op,
    outcome: r.operation.status,
  }));
  const failed = rows.filter((r) => r.operation.status === "failed");
  const applied = rows.filter((r) => r.operation.status === "applied").length;
  const tally = tallyOperations(proposal.operations);

  const columns: Column<Row>[] = [
    {
      key: "seq",
      label: "Seq",
      width: "52px",
      render: (_, row) => <span className="op-seq">{row.operation.seq}</span>,
    },
    {
      key: "op",
      label: "Op",
      width: "84px",
      render: (_, row) => <Chip variant={OP_VARIANT[row.operation.op]}>{row.operation.op}</Chip>,
    },
    {
      key: "id",
      label: "Change",
      render: (_, row) => <OperationDiff operation={row.operation} context={context} />,
    },
    {
      key: "outcome",
      label: "Outcome",
      width: "120px",
      render: (_, row) => (
        <div className="op-status" data-testid={`apply-outcome-${row.id}`}>
          <Chip variant={OPERATION_STATUS_VARIANT[row.operation.status]}>
            {row.operation.status}
          </Chip>
          {row.edited && <Chip variant="violet">edited</Chip>}
        </div>
      ),
    },
    {
      key: "result",
      label: "Result",
      width: "34%",
      render: (_, row) => (
        <div className="apply-result" data-testid={`apply-result-${row.id}`}>
          <span className="apply-result__text">{row.result}</span>
          {row.operation.status === "failed" && (
            <span className="op-decision__actions">
              {/* A failed edit retries with the edit; the server kept no record of it. */}
              {(!actions.editFailed(row.operation) || actions.lastEditOf(row.id)) && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={actions.busy}
                  onClick={() => actions.retry(row.id)}
                  data-testid={`apply-retry-${row.id}`}
                >
                  {actions.lastEditOf(row.id)
                    ? "Retry edit"
                    : row.operation.stale
                      ? "Apply anyway"
                      : "Retry"}
                </Button>
              )}
              {actions.editFailed(row.operation) && (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={actions.busy}
                  onClick={() => actions.retry(row.id, { asProposed: true })}
                  data-testid={`apply-as-proposed-${row.id}`}
                >
                  Apply as proposed
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                disabled={actions.busy}
                onClick={() => actions.rejectOperations([row.id])}
                data-testid={`apply-reject-${row.id}`}
              >
                Reject
              </Button>
            </span>
          )}
        </div>
      ),
    },
  ];

  return (
    <Panel
      className="apply-results"
      title="Apply results"
      subtitle={`${applied} of ${rows.length} applied`}
      headerAction={
        <Button
          variant="ghost"
          size="sm"
          onClick={actions.closeResults}
          data-testid="apply-results-close"
        >
          Close
        </Button>
      }
      data-testid="proposal-apply-results"
    >
      <div className="stack-lg">
        {failed.length > 0 ? (
          <FormCallout variant="warn" icon="alert" data-testid="apply-results-warning">
            {`Applied ${applied} of ${rows.length}. ${seqList(failed)} failed and stay${failed.length === 1 ? "s" : ""} failed: retry, or reject. Applies aren't atomic; each outcome is recorded, and Revert undoes everything this proposal applied.`}
          </FormCallout>
        ) : (
          <FormCallout variant="info" icon="check" data-testid="apply-results-ok">
            {`Applied ${applied} of ${rows.length}. Revert undoes everything this proposal applied.`}
          </FormCallout>
        )}
        <StatGrid columns={4} data-testid="apply-results-tally">
          <StatTile label="Applied" value={tally.applied} color="emerald" icon="check" />
          <StatTile label="Failed" value={tally.failed} color="rose" icon="alert" />
          <StatTile label="Pending" value={tally.pending} color="amber" icon="clock" />
          <StatTile label="Rejected" value={tally.rejected} color="neutral" icon="x" />
        </StatGrid>
        <div className="schema-table-wrap" data-testid="apply-results-table">
          <Table<Row> rowKey="id" columns={columns} data={rows} />
        </div>
      </div>
    </Panel>
  );
}
