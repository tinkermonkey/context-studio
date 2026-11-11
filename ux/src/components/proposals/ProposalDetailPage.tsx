import { useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Chip,
  ConfirmDialog,
  Field,
  Icon,
  PageHeader,
  ProgressBar,
  SegmentedControl,
  Table,
  TextArea,
} from "@tinkermonkey/heimdall-ui";
import { useChangeProposal, useProposalDecisions } from "@/api/hooks/proposals";
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
import { OperationDecided } from "./OperationDecided";
import { OperationDecision } from "./OperationDecision";
import { operationColumns } from "./OperationColumns";
import { OperationInspector, operationTitle } from "./OperationInspector";
import { RevertConflict } from "./RevertConflict";
import { TieredOperations } from "./TieredOperations";
import {
  DEFAULT_THRESHOLD,
  DR_TAXONOMY_IDENTIFIER,
  atOrAboveThreshold,
  decisionHeadline,
  decisionProgress,
  ANY_FACETS,
  defaultOperationFilter,
  facetCounts,
  drPredicateDescriptions,
  linksToDecided,
  operationsShown,
  nextSelection,
  hasProbabilities,
  isBlocked,
  progressPills,
  revertSummary,
  staleCause,
  staleCauseText,
  takesDecisions,
  type Facets,
  type OperationFilter,
  type RevertSummary,
} from "./decisionModel";
import {
  PROPOSAL_STATUS_VARIANT,
  formatAgo,
  isAwaiting,
  opMixLabel,
  planKind,
  refsByOperation,
} from "./proposalModel";
import {
  conflictedIds,
  defaultGroupBy,
  isBulkEligible,
  offersGroupBy,
  optionDefinition,
  pickOutcome,
  takesPicks,
  tieredOrder,
  type GroupBy,
  type Picks,
  type ReflectionOption,
} from "./tieredModel";
import { nearMatchHeldIds, nearMatchHeldNote } from "./sourceModel";
import { useOperationContext } from "./useOperationContext";
import { pendingLabel, useProposalActions } from "./useProposalActions";
import "./proposals.css";

function scopeMixLabel(operations: ProposedOperation[]): string {
  const scopes = [...new Set(operations.map((o) => o.scope))];
  if (scopes.length === 1) return `all ${scopes[0]}`;
  return (["breaking", "additive", "editorial"] as const)
    .map((scope) => [scope, operations.filter((o) => o.scope === scope).length] as const)
    .filter(([, count]) => count > 0)
    .map(([scope, count]) => `${count} ${scope}`)
    .join(" · ");
}

function revertMessage(summary: RevertSummary): string {
  const parts = [
    summary.created > 0 && `${summary.created} created removed`,
    summary.updated > 0 &&
      `${summary.updated} updated changed back${summary.edited > 0 ? ` (${summary.edited} edited)` : ""}`,
    summary.deleted > 0 && `${summary.deleted} deleted restored`,
    summary.relationships > 0 &&
      `the ${summary.relationships} relationship${summary.relationships === 1 ? "" : "s"} moved or deleted with a type restored on it`,
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
  const predicateCatalog = useMemo(() => drPredicateDescriptions(taxonomy), [taxonomy]);
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [checkedIds, setChecked] = useState<string[]>([]);
  // The operations a confirmed reject covers: all awaiting, or the checked ones.
  const [rejecting, setRejecting] = useState<{ ids: string[]; checked: boolean } | null>(null);
  const [rejectNote, setRejectNote] = useState("");
  const [confirmRevert, setConfirmRevert] = useState(false);
  // Undefined until the reviewer picks one: then it follows defaultOperationFilter.
  const [chosenFilter, setFilter] = useState<OperationFilter>();
  // The op and scope narrowing whichever primary filter is chosen.
  const [facets, setFacets] = useState<Facets>(ANY_FACETS);
  // Undefined until the reviewer picks one: then it follows defaultGroupBy.
  const [chosenGroupBy, setGroupBy] = useState<GroupBy>();
  // Reflection answers the reviewer picked over the plan's, by operation.
  const [picksByOperation, setPicksByOperation] = useState<Record<string, Picks>>({});
  // Whether the page opened (?op=) on an already decided operation: worked out
  // once, when the proposal loads, so deciding the linked operation keeps the filter.
  const openOnAll = useRef<boolean | undefined>(undefined);
  if (openOnAll.current === undefined && proposal) {
    openOnAll.current = linksToDecided(operations, selectedOperationId);
  }

  const deciding = !!proposal && takesDecisions(proposal);
  const reverted = proposal?.status === "reverted";
  const progress = useMemo(() => decisionProgress(operations, threshold), [operations, threshold]);
  const filter = chosenFilter ?? defaultOperationFilter(progress, openOnAll.current);
  const shownOperations = useMemo(
    () => operationsShown(operations, filter, facets),
    [operations, filter, facets],
  );
  const counts = useMemo(
    () => facetCounts(operations, filter, facets),
    [operations, filter, facets],
  );
  const shownIds = useMemo(() => new Set(shownOperations.map((o) => o.id)), [shownOperations]);
  const decisionsQuery = useProposalDecisions(
    proposal?.taxonomy_id ?? "",
    id,
    !!proposal && !reverted && progress.awaiting < progress.total,
  );
  // A reverted proposal's decisions no longer stand: never show cached ones.
  const decisions = reverted ? undefined : decisionsQuery.data;
  const awaitingOps = useMemo(() => operations.filter(isAwaiting), [operations]);
  // Only awaiting operations the table shows stay checked once their outcomes come back.
  const checked = useMemo(
    () =>
      new Set(
        checkedIds.filter(
          (i) => awaitingOps.some((o) => o.id === i) && shownOperations.some((o) => o.id === i),
        ),
      ),
    [checkedIds, awaitingOps, shownOperations],
  );
  // A filter that hides checked rows unchecks them, so a bulk decision only covers what is shown.
  const uncheckHidden = (nextFilter: OperationFilter, nextFacets: Facets) => {
    const shown = operationsShown(operations, nextFilter, nextFacets);
    setChecked((ids) => ids.filter((i) => shown.some((o) => o.id === i)));
  };
  const chooseFilter = (next: OperationFilter) => {
    setFilter(next);
    uncheckHidden(next, facets);
  };
  const chooseFacets = (next: Facets) => {
    setFacets(next);
    uncheckHidden(filter, next);
  };
  const groupBy = offersGroupBy(operations)
    ? (chosenGroupBy ?? defaultGroupBy(operations))
    : "sequence";
  const byKind = groupBy === "kind";
  // The ids the filters show, top to bottom, as the table or the grouping lists
  // them. A conflict card can also list members the filter doesn't show: those
  // are left out, so selection never moves onto one.
  const shownOrder = useMemo(
    () =>
      byKind
        ? tieredOrder(shownOperations, operations).filter((id) => shownIds.has(id))
        : shownOperations.map((o) => o.id),
    [byKind, shownOperations, operations, shownIds],
  );
  // When a decision drops the selected operation out of the list, select the
  // one below it, so the reviewer can decide row after row. A filter or
  // grouping change, or a deep link to an operation not shown, moves nothing.
  const lastShown = useRef<{
    order: string[];
    filter: OperationFilter;
    facets: Facets;
    groupBy: GroupBy;
  }>(undefined);
  useEffect(() => {
    const last = lastShown.current;
    lastShown.current = { order: shownOrder, filter, facets, groupBy };
    const sameView =
      !!last && last.filter === filter && last.facets === facets && last.groupBy === groupBy;
    if (!selectedOperationId || !last || !sameView) return;
    if (!last.order.includes(selectedOperationId) || shownOrder.includes(selectedOperationId))
      return;
    onSelectOperation(nextSelection(last.order, shownOrder, selectedOperationId));
  }, [shownOrder, filter, facets, groupBy, selectedOperationId, onSelectOperation]);
  // Judgment and conflict rows of a change plan are never bulk-decided.
  // So are the operations a conflict card shows, in either view.
  const conflicted = useMemo(() => conflictedIds(operations), [operations]);
  // Near matches, and what names them by "$ref", wait for the reviewer's choice:
  // a bulk accept would create a new individual for each instead.
  const nearHeld = useMemo(() => nearMatchHeldIds(operations), [operations]);
  const bulkOps = useMemo(
    () => awaitingOps.filter((o) => isBulkEligible(o, conflicted) && !nearHeld.has(o.id)),
    [awaitingOps, conflicted, nearHeld],
  );
  const bulkReady = bulkOps.filter((o) => !o.stale && !isBlocked(o));
  const showThreshold =
    !byKind && deciding && awaitingOps.length > 0 && hasProbabilities(operations);
  // The threshold picks only from what the filters show, so it never checks hidden rows.
  const shownAwaiting = awaitingOps.filter((o) => shownIds.has(o.id)).length;
  const matching = showThreshold
    ? atOrAboveThreshold(
        bulkOps.filter((o) => shownIds.has(o.id)),
        threshold,
      )
    : [];
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
              eligible: (row) => isBulkEligible(row, conflicted),
            }
          : undefined,
        reverted,
      }),
    [context, showPlanKind, showThreshold, threshold, selectable, checked, reverted, conflicted],
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

  const taxonomyLabel = taxonomy?.identifier ?? proposal.taxonomy_id;
  const isDr = taxonomy?.identifier === DR_TAXONOMY_IDENTIFIER;
  const proposedBy = proposal.source_detail ? ` by ${proposal.source_detail}` : "";
  const subtitle = [proposal.rationale, `Proposed ${formatAgo(proposal.created_at)}${proposedBy}.`]
    .filter(Boolean)
    .join(" ");
  const emptyMessage =
    operations.length === 0
      ? "This proposal has no operations."
      : facets.op !== "any" || facets.scope !== "any"
        ? "No operations match these filters."
        : filter === "needs"
          ? "Nothing needs a decision."
          : "Nothing is decided yet.";
  // A reflection answer's definition: a class's description; a predicate's
  // curated catalog entry, else the description of the type the operation changes.
  const definitionOf =
    (operation: ProposedOperation) => (question: string, option: ReflectionOption) =>
      optionDefinition(question, option, {
        classDefinition: context.classDefinition,
        predicateDefinition: (predicate) => {
          const current = context.currentProperty(operation.target_id) as
            | { canonical_predicate?: string | null; description?: string | null }
            | undefined;
          const own = current?.canonical_predicate === predicate ? current.description : undefined;
          return predicateCatalog.get(predicate) ?? (own || undefined);
        },
      });
  const causeOf = (operation: ProposedOperation) =>
    staleCause(
      operation,
      context.currentProperty(operation.target_id) as Record<string, unknown> | undefined,
      context.targetGone(operation),
    );
  const checkedList = [...checked];
  // A blocked delete counts as blocked even when stale too: Accept selected skips it either way.
  const checkedStale = operations.filter(
    (o) => checked.has(o.id) && o.stale && !isBlocked(o) && !nearHeld.has(o.id),
  ).length;
  const checkedBlocked = operations.filter(
    (o) => checked.has(o.id) && isBlocked(o) && !nearHeld.has(o.id),
  ).length;
  const checkedNear = operations.filter((o) => checked.has(o.id) && nearHeld.has(o.id));
  const heldAwaiting = awaitingOps.filter((o) => nearHeld.has(o.id));
  const awaitingIds = awaitingOps.map((o) => o.id);
  const bulkIds = bulkOps.map((o) => o.id);
  const neverBulk = awaitingOps.length - bulkOps.length;
  const blockedAwaiting = progress.needChoice;
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

      <div
        className={[
          "proposal-summary",
          deciding && (progress.awaiting > 0 ? "proposal-summary--open" : "proposal-summary--done"),
        ]
          .filter(Boolean)
          .join(" ")}
        aria-busy={actions.pending ? true : undefined}
        data-testid="proposal-summary"
      >
        <div className="proposal-summary__row">
          <Chip variant={PROPOSAL_STATUS_VARIANT[proposal.status]} data-testid="proposal-status">
            {proposal.status}
          </Chip>
          <div className="proposal-summary__progress">
            <span className="proposal-summary__tally" data-testid="proposal-tally">
              {decisionHeadline(progress)}
            </span>
            <span className="proposal-summary__decided" data-testid="proposal-decided-counts">
              {progress.applied} applied · {progress.rejected} rejected
            </span>
          </div>
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
              {progress.applied > 0 && (
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
                    onClick={() => {
                      setRejectNote("");
                      setRejecting({ ids: awaitingIds, checked: false });
                    }}
                    data-testid="proposal-reject-all"
                  >
                    Reject all awaiting
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={actions.busy || bulkReady.length === 0}
                    title={
                      awaitingOps.length > bulkReady.length
                        ? [
                            awaitingOps.some((o) => o.stale && !isBlocked(o)) &&
                              "Stale operations are left for Apply anyway",
                            blockedAwaiting > 0 &&
                              "Blocked deletes are left for a resolution in the inspector",
                            neverBulk > heldAwaiting.length &&
                              "Judgment and conflict changes are decided one by one",
                            nearMatchHeldNote(heldAwaiting)?.replace(/\.$/, ""),
                          ]
                            .filter(Boolean)
                            .join(". ")
                        : undefined
                    }
                    onClick={() => actions.acceptFresh(bulkIds)}
                    aria-busy={actions.pending?.action === "apply" ? true : undefined}
                    data-testid="proposal-accept-all"
                  >
                    Accept {bulkReady.length} ready
                  </Button>
                </>
              )}
            </span>
          )}
        </div>
        {actions.pending && (
          <div className="proposal-summary__busy" role="status" data-testid="proposal-busy">
            <Icon name="spinner" size={14} className="spin" />
            {pendingLabel(actions.pending)}
          </div>
        )}
        {deciding && progress.awaiting > 0 && (
          <div
            className="proposal-summary__pills"
            role="group"
            aria-label="What needs a decision"
            data-testid="proposal-progress-pills"
          >
            {progressPills(progress).map((pill) => (
              <button
                key={pill.key}
                type="button"
                className="proposal-pill"
                aria-controls="proposal-operations"
                aria-label={`${pill.label}: show the operations that need a decision`}
                onClick={() => {
                  // Everything that needs a decision: the op and scope filters clear too.
                  setFilter("needs");
                  setFacets(ANY_FACETS);
                  uncheckHidden("needs", ANY_FACETS);
                }}
                data-testid={`proposal-pill-${pill.key}`}
              >
                <Chip variant={pill.variant}>{pill.label}</Chip>
              </button>
            ))}
          </div>
        )}
        <ProgressBar
          className="proposal-summary__bar"
          percent={progress.percent}
          color={progress.awaiting > 0 ? "amber" : "emerald"}
          height={4}
          label={`${progress.total - progress.awaiting} of ${progress.total} decided`}
          data-testid="proposal-progress-bar"
        />
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
          awaiting={shownAwaiting}
          onSelect={() => setChecked(matching.map((o) => o.id))}
        />
      )}

      {!byKind && selectable && checked.size > 0 && (
        <SelectionBar
          selected={checked.size}
          stale={checkedStale}
          blocked={checkedBlocked}
          nearMatches={checkedNear}
          busy={actions.busy}
          onClear={() => setChecked([])}
          onReject={() => {
            setRejectNote("");
            setRejecting({ ids: checkedList, checked: true });
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
        renderInspectorContent={(operation) => {
          const picks = picksByOperation[operation.id] ?? {};
          const picking = deciding && takesPicks(operation);
          return (
            <OperationInspector
              key={operation.id}
              operation={operation}
              operations={operations}
              context={context}
              picks={picks}
              definitionOf={definitionOf(operation)}
              onPick={
                picking
                  ? (question, option) =>
                      setPicksByOperation((all) => ({
                        ...all,
                        [operation.id]: { ...all[operation.id], [question]: option },
                      }))
                  : undefined
              }
              decision={
                deciding && isAwaiting(operation) ? (
                  <OperationDecision
                    operation={operation}
                    proposal={proposal}
                    taxonomy={taxonomy}
                    current={context.currentProperty(operation.target_id)}
                    staleCause={operation.stale ? causeOf(operation) : undefined}
                    actions={actions}
                    picks={
                      operation.reflection ? pickOutcome(operation.reflection, picks) : undefined
                    }
                  />
                ) : !isAwaiting(operation) ? (
                  <OperationDecided
                    operation={operation}
                    decision={decisions?.find((d) => d.operation_id === operation.id)}
                    reverted={reverted}
                  />
                ) : undefined
              }
              reverted={reverted}
            />
          );
        }}
      >
        <div className="proposal-table-filter" data-testid="proposal-operation-filter">
          {offersGroupBy(operations) && (
            <span className="proposal-group-by" data-testid="proposal-group-by">
              <span className="proposal-bar__label">Group by</span>
              <SegmentedControl
                value={groupBy}
                onChange={(value) => setGroupBy(value as GroupBy)}
                aria-label="Group operations by"
                options={[
                  { value: "kind", label: "Change kind" },
                  { value: "sequence", label: "Sequence" },
                ]}
              />
            </span>
          )}
          <SegmentedControl
            value={filter}
            onChange={(value) => chooseFilter(value as OperationFilter)}
            aria-label="Show operations"
            options={[
              { value: "needs", label: `Needs decision · ${progress.awaiting}` },
              { value: "decided", label: `Decided · ${progress.total - progress.awaiting}` },
              { value: "all", label: `All · ${progress.total}` },
            ]}
          />
          {counts.ops.length > 1 && (
            <div data-testid="proposal-op-filter">
              <SegmentedControl
                value={facets.op}
                onChange={(value) => chooseFacets({ ...facets, op: value as Facets["op"] })}
                aria-label="Show operations by op"
                options={[
                  { value: "any", label: "Any op" },
                  ...counts.ops.map(({ value, count }) => ({
                    value,
                    label: `${value} · ${count}`,
                  })),
                ]}
              />
            </div>
          )}
          {counts.scopes.length > 1 && (
            <div data-testid="proposal-scope-filter">
              <SegmentedControl
                value={facets.scope}
                onChange={(value) => chooseFacets({ ...facets, scope: value as Facets["scope"] })}
                aria-label="Show operations by scope"
                options={[
                  { value: "any", label: "Any scope" },
                  ...counts.scopes.map(({ value, count }) => ({
                    value,
                    label: `${value} · ${count}`,
                  })),
                ]}
              />
            </div>
          )}
        </div>
        {/* Above the table, so the table frame is the last thing in the list
            column and its sticky header never scrolls under the topbar. */}
        <p className="proposals-footnote">
          {proposal.status === "reverted"
            ? "This proposal was reverted: what it applied is undone, and it takes no more decisions."
            : `Amber marks the part of a triple or the field an update changes.${showThreshold || byKind ? " Probabilities below the threshold are muted." : ""} Select an operation to see its change, rationale and evidence.`}
        </p>
        <div
          ref={tableRef}
          id="proposal-operations"
          className="schema-table-wrap"
          data-testid="proposal-operations-table"
          data-filter={filter}
          data-group-by={groupBy}
        >
          {byKind ? (
            <TieredOperations
              operations={shownOperations}
              allOperations={operations}
              context={context}
              deciding={deciding}
              reverted={reverted}
              threshold={threshold}
              onThresholdChange={setThreshold}
              actions={actions}
              selectedOperationId={selectedOperationId}
              onSelectOperation={onSelectOperation}
              emptyMessage={emptyMessage}
            />
          ) : (
            <Table<ProposedOperation>
              rowKey="id"
              columns={columns}
              data={shownOperations}
              selectedRows={selectedOperationId ? [selectedOperationId] : []}
              onRowClick={(row) =>
                onSelectOperation(row.id === selectedOperationId ? undefined : row.id)
              }
              emptyState={<span className="entity-note">{emptyMessage}</span>}
            />
          )}
        </div>
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
        isOpen={rejecting !== null}
        onClose={() => setRejecting(null)}
        onConfirm={async () => {
          if (!rejecting) return;
          setRejecting(null);
          const done = await actions.rejectOperations(rejecting.ids, rejectNote);
          if (done && rejecting.checked) setChecked([]);
        }}
        title={
          rejecting?.checked
            ? `Reject ${rejecting.ids.length} selected?`
            : `Reject all ${rejecting?.ids.length ?? 0} awaiting?`
        }
        message={
          <div className="stack">
            <p>
              A rejected operation can&apos;t be applied later. Operations already applied stay
              applied.
            </p>
            <Field
              label="Reason"
              hint="optional, stored with each reject"
              htmlFor="proposal-reject-note"
            >
              <TextArea
                id="proposal-reject-note"
                rows={2}
                value={rejectNote}
                placeholder={rejecting?.ids.length === 1 ? "Why reject it?" : "Why reject them?"}
                onChange={(e) => setRejectNote(e.target.value)}
                data-testid="proposal-reject-note"
              />
            </Field>
          </div>
        }
        confirmLabel={`Reject ${rejecting?.ids.length ?? 0}`}
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
