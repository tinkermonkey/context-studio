import { useMemo } from "react";
import { FormCallout, InspectorPanel, Table, type Column } from "@tinkermonkey/heimdall-ui";
import { useChangeProposals } from "@/api/hooks/proposals";
import { usePropertiesByIds } from "@/api/hooks/ontology/useProperties";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import { OperationDiff } from "@/components/proposals/OperationDiff";
import { ProposalLink } from "@/components/proposals/ProposalLink";
import {
  formatProbability,
  operationTouchesClass,
  type TripleSource,
} from "@/components/proposals/proposalModel";
import { useOperationContext } from "@/components/proposals/useOperationContext";
import "@/components/proposals/proposals.css";

/** The list API's maximum page: every open proposal, in the one query the queue also uses. */
const OPEN_PROPOSALS = { status: "open", limit: 500 } as const;

/** Rows shown before the "and N more" note. */
const MAX_ROWS = 8;

export type PendingEntityKind = "class" | "property" | "taxonomy";

interface PendingRow {
  id: string;
  operation: ProposedOperation;
  proposal: ChangeProposal;
}

/**
 * A class: the target, or a property operation's domain or range (the current
 * property supplies an update's untouched ends). A property: the target. A
 * taxonomy: any operation in a proposal about it, or the target.
 */
function touches(
  kind: PendingEntityKind,
  id: string,
  { proposal, operation: op }: PendingRow,
  currentProperty?: TripleSource,
) {
  switch (kind) {
    case "class":
      return operationTouchesClass(op, id, currentProperty);
    case "property":
      return op.target_id === id;
    case "taxonomy":
      return proposal.taxonomy_id === id || op.target_id === id;
  }
}

const NOUN: Record<PendingEntityKind, string> = {
  class: "class",
  property: "relationship type",
  taxonomy: "taxonomy",
};

interface PendingProposalOperationsProps {
  kind: PendingEntityKind;
  entityId: string;
  /** Render as an InspectorPanel section (inside a drawer) rather than a page block. */
  inInspector?: boolean;
}

/**
 * The pending operations in open proposals that would change this entity,
 * each linking to the operation on its proposal page. Renders nothing when
 * there are none.
 */
export function PendingProposalOperations({
  kind,
  entityId,
  inInspector,
}: PendingProposalOperationsProps) {
  const { data } = useChangeProposals(OPEN_PROPOSALS);
  const pending = useMemo<PendingRow[]>(
    () =>
      (data?.items ?? []).flatMap((proposal) =>
        proposal.operations
          .filter((op) => op.status === "pending")
          .map((operation) => ({ id: operation.id, operation, proposal })),
      ),
    [data],
  );
  // On a class page, a property update's base lacks the ends it doesn't change.
  const targetIds = useMemo(
    () =>
      kind === "class"
        ? pending
            .filter((row) => row.operation.kind === "property" && row.operation.op !== "create")
            .map((row) => row.operation.target_id)
        : [],
    [kind, pending],
  );
  const { data: targets } = usePropertiesByIds(targetIds);
  const rows = useMemo(() => {
    const byId = new Map((targets?.items ?? []).map((p) => [p.id, p]));
    return pending.filter((row) =>
      touches(kind, entityId, row, byId.get(row.operation.target_id ?? "")),
    );
  }, [pending, targets, kind, entityId]);
  const operations = useMemo(() => rows.map((row) => row.operation), [rows]);
  const context = useOperationContext(operations);

  if (rows.length === 0) return null;

  const proposalCount = new Set(rows.map((row) => row.proposal.id)).size;
  const columns: Column<PendingRow>[] = [
    {
      key: "operation",
      label: "Pending change",
      render: (_, row) => (
        <div className="pending-ops__change">
          <ProposalLink
            proposalId={row.proposal.id}
            operationId={row.operation.id}
            data-testid={`pending-operation-link-${row.operation.id}`}
          >
            <OperationDiff operation={row.operation} context={context} />
          </ProposalLink>
          <span className="pending-ops__where">
            {row.proposal.title} · seq {row.operation.seq} · {row.operation.op}
            {row.operation.stale ? " · stale" : ""}
          </span>
        </div>
      ),
    },
    {
      key: "proposal",
      label: "P",
      width: "56px",
      render: (_, row) => (
        <span className="op-probability">{formatProbability(row.operation.probability)}</span>
      ),
    },
  ];

  const body = (
    <div className="pending-ops" data-testid="pending-operations">
      <FormCallout variant="info" icon="gitBranch" data-testid="pending-operations-callout">
        {`${rows.length} pending operation${rows.length === 1 ? "" : "s"} in ${proposalCount} proposal${proposalCount === 1 ? "" : "s"} would change this ${NOUN[kind]}.`}
      </FormCallout>
      <Table<PendingRow> rowKey="id" columns={columns} data={rows.slice(0, MAX_ROWS)} />
      {rows.length > MAX_ROWS && (
        <p className="entity-note">
          Showing {MAX_ROWS} of {rows.length}; the rest are on the proposal page.
        </p>
      )}
    </div>
  );

  return inInspector ? (
    <InspectorPanel.Section title="Pending changes" count={rows.length}>
      {body}
    </InspectorPanel.Section>
  ) : (
    body
  );
}
