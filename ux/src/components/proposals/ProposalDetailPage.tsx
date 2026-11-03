import { useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Chip,
  ConfirmDialog,
  Icon,
  PageHeader,
  Table,
  type Column,
} from "@tinkermonkey/heimdall-ui";
import { useChangeProposal } from "@/api/hooks/proposals";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { ApiError } from "@/api/client/interceptors";
import type { ProposedOperation } from "@/api/services/proposals";
import { SchemaPageLayout } from "@/components/schema/SchemaPageLayout";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { linkPath } from "@/lib/entityPaths";
import { ApplyResults } from "./ApplyResults";
import { SelectionBar, ThresholdBar } from "./DecisionBars";
import { OperationDecision } from "./OperationDecision";
import { OperationDiff } from "./OperationDiff";
import { OperationInspector, operationTitle } from "./OperationInspector";
import { RevertConflict } from "./RevertConflict";
import {
  DEFAULT_THRESHOLD,
  DR_TAXONOMY_IDENTIFIER,
  atOrAboveThreshold,
  hasProbabilities,
  isBelowThreshold,
  revertSummary,
  staleCause,
  staleCauseText,
  takesDecisions,
  type RevertSummary,
} from "./decisionModel";
import {
  OPERATION_STATUS_VARIANT,
  OP_VARIANT,
  PROPOSAL_STATUS_VARIANT,
  formatAgo,
  formatProbability,
  isAwaiting,
  opMixLabel,
  planKind,
  refsByOperation,
  tallyLabel,
  tallyOperations,
} from "./proposalModel";
import { useOperationContext, type OperationContext } from "./useOperationContext";
import { useProposalActions } from "./useProposalActions";
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

interface ColumnOptions {
  showPlanKind: boolean;
  /** Probabilities below it are muted; undefined without a threshold bar. */
  threshold?: number;
  /** Checkbox selection of awaiting operations, while the proposal takes decisions. */
  selection?: { checked: Set<string>; toggle: (id: string) => void };
}

function operationColumns(context: OperationContext, options: ColumnOptions): OperationColumn[] {
  const { showPlanKind, threshold, selection } = options;
  return [
    ...(selection
      ? [
          {
            key: "id",
            label: "",
            width: "34px",
            render: (_: unknown, row: ProposedOperation) => (
              <input
                type="checkbox"
                className="table__checkbox"
                checked={selection.checked.has(row.id)}
                disabled={!isAwaiting(row)}
                onChange={() => selection.toggle(row.id)}
                onClick={(e) => e.stopPropagation()}
                aria-label={`Select operation ${row.seq}`}
                data-testid={`operation-check-${row.id}`}
              />
            ),
          } as OperationColumn,
        ]
      : []),
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
      render: (value, row) => (
        <span
          className={
            threshold !== undefined && isBelowThreshold(row, threshold)
              ? "op-probability op-probability--below"
              : "op-probability"
          }
          data-testid={`operation-probability-${row.id}`}
        >
          {formatProbability(value as number | null)}
        </span>
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
          {row.applied_fields && <Chip variant="violet">edited</Chip>}
        </div>
      ),
    },
  ];
}

function revertMessage(summary: RevertSummary): string {
  const parts = [
    summary.created > 0 && `${summary.created} created removed`,
    summary.updated > 0 &&
      `${summary.updated} updated changed back${summary.edited > 0 ? ` (${summary.edited} edited)` : ""}`,
    summary.deleted > 0 && `${summary.deleted} deleted restored`,
  ].filter(Boolean);
  const open =
    summary.open > 0
      ? ` The ${summary.open} operation${summary.open === 1 ? "" : "s"} still awaiting a decision ${summary.open === 1 ? "is" : "are"} rejected.`
      : "";
  return (
    `Undoes the ${summary.applied} operation${summary.applied === 1 ? "" : "s"} this proposal applied, in one transaction: ${parts.join(", ")}.` +
    `${open} The proposal becomes reverted and read-only, and its decisions can no longer be exported.`
  );
}

interface ProposalDetailPageProps {
  id: string;
  /** The operation shown in the inspector. */
  selectedOperationId?: string;
  onSelectOperation: (operationId: string | undefined) => void;
}

/**
 * One proposal: its tally and op mix, the operations with their changes, and
 * the selected operation in the inspector. Until it is reverted, the reviewer
 * decides here: accept or reject operations one at a time, by selection, by
 * probability threshold or all at once, edit a DR triple before accepting it,
 * and revert what the proposal applied.
 */
export function ProposalDetailPage({
  id,
  selectedOperationId,
  onSelectOperation,
}: ProposalDetailPageProps) {
  const { data: proposal, error, refetch } = useChangeProposal(id);
  const { data: taxonomy } = useTaxonomy(proposal?.taxonomy_id ?? "");
  const operations = useMemo(() => proposal?.operations ?? [], [proposal]);
  const refs = useMemo(() => (proposal ? refsByOperation([proposal]) : undefined), [proposal]);
  const context = useOperationContext(operations, refs);
  const actions = useProposalActions(proposal);
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [checkedIds, setChecked] = useState<string[]>([]);
  const [confirmRejectAll, setConfirmRejectAll] = useState(false);
  const [confirmRevert, setConfirmRevert] = useState(false);

  const deciding = !!proposal && takesDecisions(proposal);
  const awaitingOps = useMemo(() => operations.filter(isAwaiting), [operations]);
  // Only awaiting operations stay checked once their outcomes come back.
  const checked = useMemo(
    () => new Set(checkedIds.filter((i) => awaitingOps.some((o) => o.id === i))),
    [checkedIds, awaitingOps],
  );
  const showThreshold = deciding && awaitingOps.length > 0 && hasProbabilities(operations);
  const matching = showThreshold ? atOrAboveThreshold(operations, threshold) : [];
  const showPlanKind = operations.some((o) => planKind(o) !== undefined);
  const selectable = deciding && awaitingOps.length > 0;
  const columns = useMemo(
    () =>
      operationColumns(context, {
        showPlanKind,
        threshold: showThreshold ? threshold : undefined,
        selection: selectable
          ? {
              checked,
              toggle: (opId) =>
                setChecked((ids) =>
                  ids.includes(opId) ? ids.filter((i) => i !== opId) : [...ids, opId],
                ),
            }
          : undefined,
      }),
    [context, showPlanKind, showThreshold, threshold, selectable, checked],
  );

  // A deep link (?op=) scrolls its row into view once the operations load.
  const tableRef = useRef<HTMLDivElement>(null);
  const deepLinkedOperation = useRef(selectedOperationId);
  useEffect(() => {
    const target = deepLinkedOperation.current;
    if (!target || operations.length === 0) return;
    deepLinkedOperation.current = undefined;
    const row = tableRef.current?.querySelector(`tr[data-row-key="${CSS.escape(target)}"]`);
    row?.scrollIntoView?.({ block: "center" });
  }, [operations]);

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
  const isDr = taxonomy?.identifier === DR_TAXONOMY_IDENTIFIER;
  const proposedBy = proposal.source_detail ? ` by ${proposal.source_detail}` : "";
  const subtitle = [proposal.rationale, `Proposed ${formatAgo(proposal.created_at)}${proposedBy}.`]
    .filter(Boolean)
    .join(" ");
  const causeOf = (operation: ProposedOperation) =>
    staleCause(
      operation,
      context.currentProperty(operation.target_id) as Record<string, unknown> | undefined,
      context.targetGone(operation),
    );
  const checkedList = [...checked];
  const checkedStale = operations.filter((o) => checked.has(o.id) && o.stale).length;
  const awaitingIds = awaitingOps.map((o) => o.id);
  const freshAwaiting = awaitingOps.filter((o) => !o.stale).length;
  const force = actions.forceRequest;
  const forceStale = force
    ? operations.filter((o) => force.operationIds.includes(o.id) && o.stale)
    : [];
  const forceOthers = force ? force.operationIds.length - forceStale.length : 0;

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
        {deciding && (
          <span className="proposal-summary__actions" data-testid="proposal-actions">
            {isDr && (
              <Button
                variant="ghost"
                size="sm"
                disabled={actions.exporting}
                onClick={actions.downloadDecisions}
                data-testid="proposal-export-decisions"
              >
                <Icon name="download" size={13} /> Export decisions
              </Button>
            )}
            {tally.applied > 0 && (
              <Button
                variant="ghost"
                size="sm"
                disabled={actions.busy}
                onClick={() => setConfirmRevert(true)}
                data-testid="proposal-revert"
              >
                <Icon name="reload" size={13} /> Revert proposal
              </Button>
            )}
            {awaitingOps.length > 0 && (
              <>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={actions.busy}
                  onClick={() => setConfirmRejectAll(true)}
                  data-testid="proposal-reject-all"
                >
                  Reject all awaiting
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={actions.busy || freshAwaiting === 0}
                  title={
                    awaitingOps.length > freshAwaiting
                      ? "Stale operations are left for Apply anyway"
                      : undefined
                  }
                  onClick={() => actions.acceptFresh(awaitingIds)}
                  data-testid="proposal-accept-all"
                >
                  Accept all awaiting
                </Button>
              </>
            )}
          </span>
        )}
      </div>

      {actions.revertConflict && (
        <RevertConflict
          proposal={proposal}
          conflict={actions.revertConflict}
          onDismiss={actions.dismissRevertConflict}
        />
      )}

      {actions.lastApplied && (
        <ApplyResults
          proposal={proposal}
          operationIds={actions.lastApplied}
          context={context}
          actions={actions}
        />
      )}

      {showThreshold && (
        <ThresholdBar
          threshold={threshold}
          onThresholdChange={setThreshold}
          matching={matching.length}
          awaiting={awaitingOps.length}
          onSelect={() => setChecked(matching.map((o) => o.id))}
        />
      )}

      {selectable && checked.size > 0 && (
        <SelectionBar
          selected={checked.size}
          stale={checkedStale}
          busy={actions.busy}
          onClear={() => setChecked([])}
          onReject={async () => {
            if (await actions.rejectOperations(checkedList)) setChecked([]);
          }}
          onAccept={async () => {
            await actions.acceptFresh(checkedList);
            setChecked([]);
          }}
        />
      )}

      <SchemaPageLayout
        data={operations}
        selectedId={selectedOperationId}
        renderInspectorContent={(operation) => (
          <OperationInspector
            key={operation.id}
            operation={operation}
            context={context}
            decision={
              deciding && isAwaiting(operation) ? (
                <OperationDecision
                  operation={operation}
                  proposal={proposal}
                  taxonomy={taxonomy}
                  current={context.currentProperty(operation.target_id)}
                  staleCause={operation.stale ? causeOf(operation) : undefined}
                  actions={actions}
                />
              ) : undefined
            }
          />
        )}
      >
        <div ref={tableRef} className="schema-table-wrap" data-testid="proposal-operations-table">
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
          {proposal.status === "reverted"
            ? "This proposal was reverted: what it applied is undone, and it takes no more decisions."
            : `Amber marks the part of a triple or the field an update changes.${showThreshold ? " Probabilities below the threshold are muted." : ""} Select an operation to see its change, rationale and evidence.`}
        </p>
      </SchemaPageLayout>

      <ConfirmDialog
        isOpen={!!force}
        onClose={actions.cancelForce}
        onConfirm={actions.confirmForce}
        title="Apply anyway?"
        message={
          <div className="stack" data-testid="proposal-force-message">
            <p>
              {forceStale.length === 1 ? "This operation's" : "These operations'"} target changed
              after {forceStale.length === 1 ? "it was" : "they were"} proposed. Applying keeps the
              proposed values over those changes; a target that is gone fails with target_missing.
            </p>
            <ul className="proposal-force-list">
              {forceStale.map((o) => (
                <li key={o.id}>
                  <span className="op-seq">seq {o.seq}</span> {operationTitle(o, context)}:{" "}
                  {staleCauseText(causeOf(o))}
                </li>
              ))}
            </ul>
            {forceOthers > 0 && (
              <p>
                {forceOthers} other operation{forceOthers === 1 ? "" : "s"} apply with{" "}
                {forceStale.length === 1 ? "it" : "them"}.
              </p>
            )}
          </div>
        }
        confirmLabel="Apply anyway"
        variant="primary"
      />

      <ConfirmDialog
        isOpen={confirmRejectAll}
        onClose={() => setConfirmRejectAll(false)}
        onConfirm={() => {
          setConfirmRejectAll(false);
          void actions.rejectOperations(awaitingIds);
        }}
        title={`Reject all ${awaitingIds.length} awaiting?`}
        message="A rejected operation can't be applied later. Operations already applied stay applied."
        confirmLabel={`Reject ${awaitingIds.length}`}
      />

      <ConfirmDialog
        isOpen={confirmRevert}
        onClose={() => setConfirmRevert(false)}
        onConfirm={() => {
          setConfirmRevert(false);
          void actions.revertProposal();
        }}
        title="Revert this proposal?"
        message={
          <span data-testid="proposal-revert-message">
            {revertMessage(revertSummary(proposal))}
          </span>
        }
        confirmLabel="Revert proposal"
      />
    </div>
  );
}
