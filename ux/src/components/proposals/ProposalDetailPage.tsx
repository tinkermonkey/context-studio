import { useMemo } from "react";
import { Chip, PageHeader, Table, type Column } from "@tinkermonkey/heimdall-ui";
import { useChangeProposal } from "@/api/hooks/proposals";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { ApiError } from "@/api/client/interceptors";
import type { ProposedOperation } from "@/api/services/proposals";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { linkPath } from "@/lib/entityPaths";
import { OperationDiff } from "./OperationDiff";
import { OperationInspector } from "./OperationInspector";
import {
  OPERATION_STATUS_VARIANT,
  OP_VARIANT,
  PROPOSAL_STATUS_VARIANT,
  formatAge,
  formatProbability,
  opMixLabel,
  planKind,
  tallyLabel,
  tallyOperations,
} from "./proposalModel";
import { useOperationContext, type OperationContext } from "./useOperationContext";
import "./proposals.css";

type OperationColumn = Column<ProposedOperation>;

function scopeMixLabel(operations: ProposedOperation[]): string {
  const scopes = [...new Set(operations.map((o) => o.scope))];
  if (scopes.length === 1) return `all ${scopes[0]}`;
  return (["breaking", "additive", "editorial"] as const)
    .map((scope) => [scope, operations.filter((o) => o.scope === scope).length] as const)
    .filter(([, count]) => count > 0)
    .map(([scope, count]) => `${count} ${scope}`)
    .join(" · ");
}

function operationColumns(context: OperationContext, showPlanKind: boolean): OperationColumn[] {
  return [
    {
      key: "seq",
      label: "Seq",
      width: "52px",
      render: (value) => <span className="op-seq">{value as number}</span>,
    },
    {
      key: "op",
      label: "Op",
      width: "84px",
      render: (value) => (
        <Chip variant={OP_VARIANT[value as ProposedOperation["op"]]}>{value as string}</Chip>
      ),
    },
    {
      key: "fields",
      label: "Change",
      render: (_, row) => <OperationDiff operation={row} context={context} />,
    },
    ...(showPlanKind
      ? [
          {
            key: "rationale",
            label: "Plan kind",
            width: "140px",
            render: (_: unknown, row: ProposedOperation) => (
              <span className="op-plan-kind">{planKind(row) ?? "—"}</span>
            ),
          } as OperationColumn,
        ]
      : []),
    {
      key: "probability",
      label: "P",
      width: "56px",
      render: (value) => (
        <span className="op-probability">{formatProbability(value as number | null)}</span>
      ),
    },
    {
      key: "status",
      label: "Status",
      width: "110px",
      render: (_, row) => (
        <div className="op-status" data-testid={`operation-status-${row.id}`}>
          <Chip variant={OPERATION_STATUS_VARIANT[row.status]}>{row.status}</Chip>
          {row.stale && (
            <Chip variant="rose" data-testid={`operation-stale-${row.id}`}>
              stale
            </Chip>
          )}
        </div>
      ),
    },
  ];
}

interface ProposalDetailPageProps {
  id: string;
  /** The operation shown in the inspector. */
  selectedOperationId?: string;
  onSelectOperation: (operationId: string | undefined) => void;
}

/**
 * One proposal, read-only: its tally and op mix, the operations with their
 * changes, and the selected operation in the inspector.
 */
export function ProposalDetailPage({
  id,
  selectedOperationId,
  onSelectOperation,
}: ProposalDetailPageProps) {
  const { data: proposal, error, refetch } = useChangeProposal(id);
  const { data: taxonomy } = useTaxonomy(proposal?.taxonomy_id ?? "");
  const operations = useMemo(() => proposal?.operations ?? [], [proposal]);
  const context = useOperationContext(operations);
  const showPlanKind = operations.some((o) => planKind(o) !== undefined);
  const columns = useMemo(() => operationColumns(context, showPlanKind), [context, showPlanKind]);

  usePageBreadcrumbs(
    linkPath("proposal", id),
    proposal ? [{ label: "Proposals", to: "/app/proposals" }, { label: proposal.title }] : null,
  );

  if (error) {
    return error instanceof ApiError && error.status === 404 ? (
      <EmptyState
        title="Proposal not found"
        description="This proposal doesn't exist. It may have been removed."
      />
    ) : (
      <ErrorBanner error={error} onRetry={() => refetch()} message="Failed to load proposal" />
    );
  }

  if (!proposal) {
    return (
      <div className="stack-lg" data-testid="proposal-page">
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      </div>
    );
  }

  const tally = tallyOperations(operations);
  const taxonomyLabel = taxonomy?.identifier ?? proposal.taxonomy_id;
  const proposedBy = proposal.source_detail ? ` by ${proposal.source_detail}` : "";
  const subtitle = [
    proposal.rationale,
    `Proposed ${formatAge(proposal.created_at)} ago${proposedBy}.`,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="stack-lg" data-testid="proposal-page">
      <PageHeader
        eyebrow={`PROPOSAL · ${taxonomyLabel} · ${proposal.source}`}
        title={proposal.title}
        idChip={proposal.id.slice(0, 8)}
        subtitle={subtitle}
      />

      <div className="proposal-summary" data-testid="proposal-summary">
        <Chip variant={PROPOSAL_STATUS_VARIANT[proposal.status]} data-testid="proposal-status">
          {proposal.status}
        </Chip>
        <span className="proposal-summary__tally" data-testid="proposal-tally">
          {tallyLabel(tally)}
        </span>
        <span className="proposal-summary__mix" data-testid="proposal-op-mix">
          {opMixLabel(operations)} · {scopeMixLabel(operations)}
        </span>
      </div>

      <SchemaPageLayout
        data={operations}
        selectedId={selectedOperationId}
        renderInspectorContent={(operation) => (
          // #1361 passes the Decision section (accept / reject / edit) as `decision`.
          <OperationInspector key={operation.id} operation={operation} context={context} />
        )}
      >
        <div className="schema-table-wrap" data-testid="proposal-operations-table">
          <Table<ProposedOperation>
            rowKey="id"
            columns={columns}
            data={operations}
            selectedRows={selectedOperationId ? [selectedOperationId] : []}
            onRowClick={(row) =>
              onSelectOperation(row.id === selectedOperationId ? undefined : row.id)
            }
            emptyState={<span className="entity-note">This proposal has no operations.</span>}
          />
        </div>
        <p className="proposals-footnote">
          Amber marks the part of a triple or the field an update changes. Select an operation to
          see its change, rationale and evidence.
        </p>
      </SchemaPageLayout>
    </div>
  );
}
