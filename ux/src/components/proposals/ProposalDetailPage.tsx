import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  Button,
  Chip,
  ConfirmDialog,
  Field,
  Icon,
  PageHeader,
  ProgressBar,
  PaneRail,
  SegmentedControl,
  TextArea,
  type PaneRailMark,
} from "@tinkermonkey/heimdall-ui";
import { useChangeProposal, useProposalDecisions } from "@/api/hooks/proposals";
import { useTaxonomy } from "@/api/hooks/ontology/useTaxonomies";
import { useTaxonomyPredicates } from "@/api/hooks/ontology/usePredicates";
import { ApiError } from "@/api/client/interceptors";
import type { ProposedOperation, RejectionReason } from "@/api/services/proposals";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { linkPath } from "@/lib/entityPaths";
import { ApplyResults } from "./ApplyResults";
import { OperationDiff, operationTitle } from "./OperationDiff";
import { RejectReasonPicker } from "./RejectReasonPicker";
import { RevertConflict } from "./RevertConflict";
import { RevertControl } from "./RevertControl";
import { reversalChips } from "./reversalModel";
import {
  DEFAULT_THRESHOLD,
  decidedByLabel,
  DR_TAXONOMY_IDENTIFIER,
  atOrAboveThreshold,
  decisionHeadline,
  decisionProgress,
  ANY_FACETS,
  defaultOperationFilter,
  facetCounts,
  predicateDescriptions,
  linksToDecided,
  operationsShown,
  nextSelection,
  hasProbabilities,
  isBlocked,
  progressPills,
  staleCause,
  staleCauseText,
  takesDecisions,
  type Facets,
  type OperationFilter,
} from "./decisionModel";
import {
  PROPOSAL_STATUS_VARIANT,
  formatAgo,
  formatProbability,
  isAwaiting,
  opMixLabel,
  refsByOperation,
} from "./proposalModel";
import {
  conflictedIds,
  isBulkEligible,
  optionDefinition,
  pickOutcome,
  takesPicks,
  type Picks,
  type ReflectionOption,
} from "./tieredModel";
import { nearMatchHeldIds, nearMatchHeldNote, noPassageHeldIds } from "./sourceModel";
import { ProposalLink } from "./ProposalLink";
import { ProposalOriginChip } from "./ProposalOrigin";
import { ConflictCard } from "./review/ConflictCard";
import { BulkBar, BulkSelect, type BulkPick } from "./review/ReviewBulk";
import { ReviewElementsPane, type ElementRow } from "./review/ReviewElementsPane";
import { RowFlags } from "./review/RowFlags";
import {
  GROUP_BY_LABELS,
  defaultListGroupBy,
  groupByOptions,
  listOrder,
  listSections,
  rowStatus,
  type ListGroupBy,
} from "./review/reviewList";
import {
  isElement,
  isRelationship,
  nextAwaiting,
  shownClassId,
  verdictLabel,
  verdictOf,
} from "./review/reviewModel";
import { usePaneFold, type PaneFold } from "./review/paneFold";
import { ReviewElapsed } from "./review/ReviewElapsed";
import { usePanesHeight } from "./review/usePanesHeight";
import { useReviewClock } from "./review/useReviewClock";
import { useReviewKeys, ignoresKeys } from "./review/useReviewKeys";
import { railMarkTarget, useSourcePane } from "./review/useSourcePane";
import { sourcePassagesOf } from "./sourceModel";
import { HOLDOUT_NOTE, SPLIT_CHIP, goldCheckOf } from "./review/goldModel";
import { ReviewInspector } from "./review/ReviewInspector";
import {
  IndividualCard,
  ReviewPillsProvider,
  plainClick,
  type OperationLink,
} from "./review/ReviewPills";
import { useInspectorModel } from "./review/useInspectorModel";
import { WideDiffOverlay } from "./review/WideDiffOverlay";
import { longChangeFields, stepLongChange } from "./review/wideDiff";
import { CompareEntry } from "./compare/CompareEntry";
import { useOperationContext } from "./useOperationContext";
import { pendingLabel, useProposalActions } from "./useProposalActions";
import "./proposals.css";
import "./review/review.css";

function scopeMixLabel(operations: ProposedOperation[]): string {
  const scopes = [...new Set(operations.map((o) => o.scope))];
  if (scopes.length === 1) return `all ${scopes[0]}`;
  return (["breaking", "additive", "editorial"] as const)
    .map((scope) => [scope, operations.filter((o) => o.scope === scope).length] as const)
    .filter(([, count]) => count > 0)
    .map(([scope, count]) => `${count} ${scope}`)
    .join(" · ");
}

/** Where focus goes after a fold (the rail's expand button) and an unfold (the pane's ‹). */
const FOLD_FOCUS = {
  expand: {
    source: '[data-testid="review-source-rail"] .pane-rail__expand',
    list: '[data-testid="review-list-rail"] .pane-rail__expand',
  },
  fold: {
    source: '[data-testid="review-fold-source"]',
    list: '[data-testid="review-fold-list"]',
  },
} as const;

interface ProposalDetailPageProps {
  id: string;
  /** The operation shown in the inspector. */
  selectedOperationId?: string;
  onSelectOperation: (operationId: string | undefined) => void;
  /** Open the comparison with another open proposal for the same source. */
  onCompare?: (otherId: string) => void;
  /** The long text field open in the wide diff (&diff=), if any. */
  diffField?: string;
  /**
   * Open the wide diff on a field (of another operation, for J / K), or close it
   * (undefined). Without it there is no wide diff.
   */
  onDiff?: (field: string | undefined, operationId?: string) => void;
}

/**
 * One proposal: its tally and op mix, the review list of its operations
 * (grouped by layer, change kind or sequence, conflicts as cards), and the
 * selected operation in the inspector. Until it is reverted, the reviewer
 * decides here: one at a time in the inspector or by key (A, X, J / K), or in
 * bulk (Select ▾ and the bulk bar, on every proposal but a gold check); edit a
 * DR triple before accepting it; and revert what the proposal applied.
 */
export function ProposalDetailPage({
  id,
  selectedOperationId,
  onSelectOperation,
  onCompare,
  diffField,
  onDiff,
}: ProposalDetailPageProps) {
  const { data: proposal, error, refetch } = useChangeProposal(id);
  const { data: taxonomy } = useTaxonomy(proposal?.taxonomy_id ?? "");
  const operations = useMemo(() => proposal?.operations ?? [], [proposal]);
  const refs = useMemo(() => (proposal ? refsByOperation([proposal]) : undefined), [proposal]);
  const context = useOperationContext(operations, refs);
  const actions = useProposalActions(proposal);
  const { data: predicates } = useTaxonomyPredicates(proposal?.taxonomy_id);
  const predicateDefinitions = useMemo(() => predicateDescriptions(predicates), [predicates]);
  const [threshold, setThreshold] = useState(DEFAULT_THRESHOLD);
  const [checkedIds, setChecked] = useState<string[]>([]);
  // The checked operations a confirmed reject covers.
  const [rejecting, setRejecting] = useState<{ ids: string[] } | null>(null);
  const [rejectNote, setRejectNote] = useState("");
  // One code for every operation a reject covers; "other" fits any operation.
  const [rejectCode, setRejectCode] = useState<RejectionReason>("other");
  const [confirmRevert, setConfirmRevert] = useState(false);
  // Undefined until the reviewer picks one: then it follows defaultOperationFilter.
  const [chosenFilter, setFilter] = useState<OperationFilter>();
  // The op and scope narrowing whichever primary filter is chosen.
  const [facets, setFacets] = useState<Facets>(ANY_FACETS);
  // Undefined until the reviewer picks one: then it follows defaultListGroupBy.
  const [chosenGroupBy, setGroupBy] = useState<ListGroupBy>();
  // Bumped by X: the inspector opens its reason step.
  const [rejectPrompt, setRejectPrompt] = useState(0);
  // Reflection answers the reviewer picked over the plan's, by operation.
  const [picksByOperation, setPicksByOperation] = useState<Record<string, Picks>>({});
  // Whether the page opened (?selected=) on an already decided operation: worked out
  // once, when the proposal loads, so deciding the linked operation keeps the filter.
  const openOnAll = useRef<boolean | undefined>(undefined);
  if (openOnAll.current === undefined && proposal) {
    openOnAll.current = linksToDecided(operations, selectedOperationId);
  }

  const deciding = !!proposal && takesDecisions(proposal);
  // A benchmark gold check: decided here in gold mode (tier, also defensible, the note), never in bulk.
  const goldCheck = !!goldCheckOf(proposal);
  // Gold checks are decided here too (#1664): tier, also defensible and the note are the inspector's.
  const decidesHere = deciding;
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
  const groupOptions = useMemo(() => groupByOptions(operations), [operations]);
  const groupBy =
    chosenGroupBy && groupOptions.includes(chosenGroupBy)
      ? chosenGroupBy
      : defaultListGroupBy(operations);
  // The selection: the route's when it names an operation of this proposal, else the
  // first row awaiting a decision (else the first row), without a history entry.
  const [autoSelectedId, setAutoSelectedId] = useState<string>();
  const routeSelects =
    !!selectedOperationId && operations.some((o) => o.id === selectedOperationId);
  const selectedId = routeSelects ? selectedOperationId : autoSelectedId;
  const selectedOperation = operations.find((o) => o.id === selectedId);
  // The selection the URL names: a click on it changes nothing (an auto-selected row's
  // click still puts it in the URL).
  const routeSelectedRef = useRef<string | undefined>(undefined);
  routeSelectedRef.current = routeSelects ? selectedOperationId : undefined;
  // Each decision records the active time spent on its operation.
  const clock = useReviewClock();
  useEffect(() => clock.startElement(selectedId), [clock, selectedId]);

  // The review inspector's data (classes, layers, names, the pills and their
  // hovers): one inspector for every operation.
  const inspectorLink = (operationId: string): OperationLink => ({
    href: `${linkPath("proposal", id)}?selected=${encodeURIComponent(operationId)}`,
    onClick: (event) => {
      if (!plainClick(event)) return;
      event.preventDefault();
      // Selecting what is selected changes nothing.
      if (operationId === routeSelectedRef.current) return;
      onSelectOperation(operationId);
    },
  });
  const inspector = useInspectorModel(proposal, {
    actions,
    context,
    selected: selectedOperation,
    link: inspectorLink,
    deciding: decidesHere,
    clock,
    onDecided: (decidedId, after) => {
      // Under a filter that keeps it (All, Decided), a first decision moves on to the
      // next row awaiting one; under Needs decision it drops out, and the row below takes
      // its place (see lastShown).
      if (filterRef.current === "needs") return;
      const awaiting = new Set(after.filter(isAwaiting).map((o) => o.id));
      awaiting.delete(decidedId);
      const next = nextAwaiting(shownOrderRef.current, awaiting, decidedId);
      if (next) onSelectOperation(next);
    },
  });

  // The list's sections, and its rows top to bottom (J / K, and where the
  // selection goes). A conflict card can also hold members the filter doesn't
  // show: those are left out, so selection never moves onto one.
  const sections = useMemo(
    () => listSections(shownOperations, operations, groupBy, inspector.layerOf),
    [shownOperations, operations, groupBy, inspector.layerOf],
  );
  const shownOrder = useMemo(() => listOrder(sections), [sections]);
  const filterRef = useRef(filter);
  filterRef.current = filter;
  const shownOrderRef = useRef(shownOrder);
  shownOrderRef.current = shownOrder;
  useEffect(() => {
    if (routeSelects) return;
    if (autoSelectedId && shownOrder.includes(autoSelectedId)) return;
    const first =
      shownOrder.find((opId) => operations.some((o) => o.id === opId && isAwaiting(o))) ??
      shownOrder[0];
    if (first !== autoSelectedId) setAutoSelectedId(first);
  }, [routeSelects, autoSelectedId, shownOrder, operations]);
  // When a decision drops the selected operation out of the list, select the
  // one below it, so the reviewer can decide row after row. A filter or
  // grouping change, or a deep link to an operation not shown, moves nothing.
  const lastShown = useRef<{
    order: string[];
    filter: OperationFilter;
    facets: Facets;
    groupBy: ListGroupBy;
  }>(undefined);
  useEffect(() => {
    const last = lastShown.current;
    lastShown.current = { order: shownOrder, filter, facets, groupBy };
    const sameView =
      !!last && last.filter === filter && last.facets === facets && last.groupBy === groupBy;
    if (!selectedId || !last || !sameView) return;
    if (!last.order.includes(selectedId) || shownOrder.includes(selectedId)) return;
    onSelectOperation(nextSelection(last.order, shownOrder, selectedId));
  }, [shownOrder, filter, facets, groupBy, selectedId, onSelectOperation]);
  // Judgment and conflict rows of a change plan are never bulk-decided.
  // So are the operations a conflict card shows, in any view.
  const conflicted = useMemo(() => conflictedIds(operations), [operations]);
  // Near matches, and what names them by "$ref", wait for the reviewer's choice:
  // a bulk accept would create a new individual for each instead.
  const nearHeld = useMemo(() => nearMatchHeldIds(operations), [operations]);
  const bulkOps = useMemo(
    () => awaitingOps.filter((o) => isBulkEligible(o, conflicted) && !nearHeld.has(o.id)),
    [awaitingOps, conflicted, nearHeld],
  );
  // Operations without a passage (and what names them) are held back by Accept
  // selected, which says how many: each is accepted on its own.
  const passageHeld = useMemo(() => noPassageHeldIds(operations), [operations]);
  const bulkReady = bulkOps.filter((o) => !o.stale && !isBlocked(o) && !passageHeld.has(o.id));
  // Bulk decisions on every proposal decided here (extractions included), never on a gold check.
  const bulk = decidesHere && !goldCheck && awaitingOps.length > 0;
  // Select ▾ picks only from what the filters show, so it never checks hidden rows.
  const shownBulk = bulkOps.filter((o) => shownIds.has(o.id));
  const shownReady = bulkReady.filter((o) => shownIds.has(o.id));
  const matching = hasProbabilities(operations)
    ? atOrAboveThreshold(shownReady, threshold)
    : undefined;
  // What All ready leaves out among the rows shown, and why (the menu says so).
  const shownAwaiting = awaitingOps.filter((o) => shownIds.has(o.id));
  const shownHeld = shownAwaiting.filter((o) => nearHeld.has(o.id));
  const readyLeftOut =
    [
      shownBulk.some((o) => o.stale && !isBlocked(o)) &&
        "Stale operations are left for Apply anyway",
      shownBulk.some((o) => isBlocked(o)) &&
        "Blocked deletes are left for a resolution in the inspector",
      shownAwaiting.length - shownBulk.length > shownHeld.length &&
        "Judgment and conflict changes are decided one by one",
      nearMatchHeldNote(shownHeld)?.replace(/\.$/, ""),
      shownBulk.some((o) => passageHeld.has(o.id)) &&
        "Operations without a passage are held back to accept one by one",
    ]
      .filter(Boolean)
      .join(". ") || undefined;
  const pickBulk = (pick: BulkPick) =>
    setChecked(
      (pick === "ready"
        ? shownReady
        : pick === "threshold"
          ? (matching ?? [])
          : pick === "awaiting"
            ? shownBulk
            : []
      ).map((o) => o.id),
    );

  // The wide diff (#1661): a long text change of the selected operation, read side by side
  // over the list. W opens its first long change; Esc, ✕ or Back close it, and focus
  // goes back to the Wide control of the row it was opened from.
  const wideFields = selectedOperation ? longChangeFields(selectedOperation) : [];
  const wideOpen = !!onDiff && !!diffField && wideFields.includes(diffField);
  const wideFrom = useRef<string | undefined>(undefined);
  const openWide = (field: string) => {
    wideFrom.current = field;
    onDiff?.(field);
  };
  const wasOpen = useRef(false);
  // Opened from a link (&diff= in the URL): focus goes back to that field's row.
  if (wideOpen && !wideFrom.current) wideFrom.current = diffField;
  useEffect(() => {
    if (wasOpen.current && !wideOpen && wideFrom.current) {
      const field = wideFrom.current;
      requestAnimationFrame(() =>
        document.querySelector<HTMLElement>(`[data-testid="review-wide-${field}"]`)?.focus(),
      );
    }
    wasOpen.current = wideOpen;
  }, [wideOpen]);
  const onWideKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onWideKey.current = (event) => {
    if (wideOpen || !onDiff || event.defaultPrevented || ignoresKeys(event.target)) return;
    if (event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
    if (event.key.toLowerCase() === "w" && wideFields.length > 0) {
      event.preventDefault();
      openWide(wideFields[0]);
    }
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onWideKey.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  // Either left pane folds to a rail (#1665): one at a time, remembered per viewer.
  const paneFold = usePaneFold();

  // The source pane, when the proposal was extracted from a source (#1664).
  const sourcePane = useSourcePane({
    proposal,
    operations,
    selected: selectedOperation,
    selectedId,
    select: (operationId) => onSelectOperation(operationId),
    model: inspector,
    clock,
    onFold: () => changeFold("source"),
  });
  // Only a source with its text loaded folds: without one, the list is the only way through
  // (and a rail of a source that couldn't load would map nothing).
  const canFold = sourcePane.shown && sourcePane.hasText;
  const fold = canFold ? paneFold.fold : undefined;
  // The rail mark whose hover card is open: closed when the fold changes, so none sticks.
  const railCardId = useRef<string | undefined>(undefined);
  // Whether focus was on the page or a rail when the fold changed: it then moves to the
  // control that undoes the change (see the effect below); elsewhere, it stays put.
  const refocusOnFold = useRef(false);
  const changeFold = (next: PaneFold) => {
    if (railCardId.current) inspector.overlay.hide(railCardId.current);
    railCardId.current = undefined;
    // Folding the source forgets the passage last shown, so it reopens on the selection.
    if (next === "source") sourcePane.forgetFocus();
    const active = document.activeElement;
    refocusOnFold.current =
      !active || active === document.body || !!active.closest(".pane-rail, .review-fold");
    paneFold.setFold(next);
  };
  // After a fold, focus is on the rail's expand button; after an unfold, on the pane's ‹.
  const lastFold = useRef(fold);
  useEffect(() => {
    const was = lastFold.current;
    lastFold.current = fold;
    if (was === fold || !refocusOnFold.current) return;
    refocusOnFold.current = false;
    const target = fold ? FOLD_FOCUS.expand[fold] : was ? FOLD_FOCUS.fold[was] : undefined;
    if (!target) return;
    requestAnimationFrame(() =>
      document.querySelector<HTMLElement>(target)?.focus({ preventScroll: true }),
    );
  }, [fold]);
  // [ folds or unfolds the source, ] the list (one rail at a time). Held down, once; with
  // Option or AltGr too, where a layout types [ or ] with it.
  const onFoldKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onFoldKey.current = (event) => {
    if (!canFold || sourcePane.adding || wideOpen) return;
    if (event.defaultPrevented || event.repeat || event.metaKey || event.ctrlKey) return;
    if (ignoresKeys(event.target)) return;
    if (event.key === "[") {
      event.preventDefault();
      changeFold(fold === "source" ? undefined : "source");
    } else if (event.key === "]") {
      event.preventDefault();
      changeFold(fold === "list" ? undefined : "list");
    }
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onFoldKey.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
  // An operation's title as text: an element's, a relationship's ends, else what it changes.
  const plainTitle = (operation: ProposedOperation) => {
    if (isElement(operation)) return inspector.names.titleOf(operation);
    if (isRelationship(operation) && operation.op === "create") {
      const parts = inspector.names.relationshipParts(operation);
      return `${parts.from} → ${parts.to}`;
    }
    return operationTitle(operation, context);
  };
  // A rail mark's hover: the item's pill card, beside the rail.
  const railCard = (operationId: string) => {
    const operation = operations.find((o) => o.id === operationId);
    if (!operation) return null;
    if (isElement(operation)) {
      return (
        <IndividualCard
          title={inspector.names.titleOf(operation)}
          classId={shownClassId(operation)}
          verdict={verdictOf(operation)}
          status={verdictLabel(operation)}
          quote={sourcePassagesOf(operation)[0]?.quote ?? undefined}
        />
      );
    }
    const status = rowStatus(operation, reverted);
    return (
      <div className="review-card">
        <span className="review-card__head">
          <span className="review-card__name">{plainTitle(operation)}</span>
          <Chip variant={status.variant}>{status.label}</Chip>
        </span>
      </div>
    );
  };
  const railHover = {
    onMarkHover: (markId: string, anchor: HTMLElement) => {
      railCardId.current = `rail-${markId}`;
      inspector.overlay.show(
        `rail-${markId}`,
        railCard(railMarkTarget(markId).operationId),
        anchor,
        "review-rail-card",
      );
    },
    onMarkLeave: (markId: string) => {
      inspector.overlay.hide(`rail-${markId}`);
      if (railCardId.current === `rail-${markId}`) railCardId.current = undefined;
    },
  };
  // The list rail's map: every row in list order, in its status's tone.
  const operationById = useMemo(() => new Map(operations.map((o) => [o.id, o])), [operations]);
  const listRailMarks = useMemo(
    (): PaneRailMark[] =>
      shownOrder.flatMap((operationId, index) => {
        const operation = operationById.get(operationId);
        if (!operation) return [];
        const status = rowStatus(operation, reverted);
        return [
          {
            id: operationId,
            position: index / Math.max(1, shownOrder.length - 1),
            tone: status.variant as PaneRailMark["tone"],
            label: `${status.label}: ${plainTitle(operation)}`,
          },
        ];
      }),
    // plainTitle reads the names and the context, which change with these.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [shownOrder, operationById, reverted, inspector.names, context],
  );
  const selectedIndex = selectedId ? shownOrder.indexOf(selectedId) : -1;
  const panes = usePanesHeight(!!proposal && sourcePane.shown);
  // While the add form is open, keys are its own; Escape closes it wherever focus went.
  const onAddingKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onAddingKey.current = (event) => {
    if (sourcePane.adding && event.key === "Escape" && !event.defaultPrevented) {
      sourcePane.closeAdding();
    }
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onAddingKey.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  // Keys: J / K next and previous, A accept, X the reasons, 1-3 a suggested class
  // (an element). Not while the wide diff (its own keys) or a confirmation is open.
  // A accepts as proposed only: a relationship type with picks, or a blocked delete,
  // is decided with the inspector's buttons.
  useReviewKeys({
    order: shownOrder,
    selectedId,
    select: (operationId) => onSelectOperation(operationId),
    selected: selectedOperation,
    operations,
    model: inspector,
    paused:
      wideOpen ||
      sourcePane.adding ||
      !!actions.forceRequest ||
      rejecting !== null ||
      confirmRevert,
    onReasons: () => setRejectPrompt((n) => n + 1),
    acceptsByKey: (operation) =>
      !isBlocked(operation) && Object.keys(picksByOperation[operation.id] ?? {}).length === 0,
  });

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
          return predicateDefinitions.get(predicate) ?? (own || undefined);
        },
      });
  const causeOf = (operation: ProposedOperation) =>
    staleCause(
      operation,
      context.currentProperty(operation.target_id) as Record<string, unknown> | undefined,
      context.targetGone(operation),
    );
  // A row: an element by its title and class, a relationship by its ends and
  // predicate, anything else by what it changes, inline.
  const rowOf = (operation: ProposedOperation): ElementRow => {
    const status = rowStatus(operation, reverted);
    const base = {
      probability:
        operation.probability === null || operation.probability === undefined
          ? ""
          : formatProbability(operation.probability),
      ...status,
      amended: !!operation.amended_at,
      flags: <RowFlags operation={operation} context={context} />,
    };
    if (isElement(operation)) {
      const detail = inspector.names.classLabel(shownClassId(operation));
      return { title: inspector.names.titleOf(operation), detail, detailTitle: detail, ...base };
    }
    if (isRelationship(operation) && operation.op === "create") {
      const parts = inspector.names.relationshipParts(operation);
      return {
        title: `${parts.from} → ${parts.to}`,
        detail: parts.predicate,
        detailTitle: parts.predicate,
        ...base,
      };
    }
    return {
      title: (
        <>
          <span className="review-row__seq" data-testid={`review-row-op-${operation.id}`}>
            seq {operation.seq} · {operation.op}
          </span>{" "}
          {operationTitle(operation, context)}
        </>
      ),
      change: <OperationDiff operation={operation} context={context} />,
      ...base,
    };
  };
  // A DR relationship type's decision: its picks, triple and in-use resolution.
  const typeOf = (operation: ProposedOperation) => {
    if (operation.kind !== "property") return undefined;
    const picks = picksByOperation[operation.id] ?? {};
    return {
      decision: {
        proposal,
        taxonomy,
        current: context.currentProperty(operation.target_id),
        staleCause: operation.stale ? causeOf(operation) : undefined,
        actions,
        picks: operation.reflection ? pickOutcome(operation.reflection, picks) : undefined,
      },
      current: context.currentProperty(operation.target_id),
      picks,
      onPick:
        decidesHere && takesPicks(operation)
          ? (question: string, option: string) =>
              setPicksByOperation((all) => ({
                ...all,
                [operation.id]: { ...all[operation.id], [question]: option },
              }))
          : undefined,
      definitionOf: definitionOf(operation),
    };
  };
  const checkedList = [...checked];
  // Held back first (near matches, then operations without a passage), as Accept selected does.
  const isHeld = (o: ProposedOperation) => nearHeld.has(o.id) || passageHeld.has(o.id);
  // A blocked delete counts as blocked even when stale too: Accept selected skips it either way.
  const checkedStale = operations.filter(
    (o) => checked.has(o.id) && o.stale && !isBlocked(o) && !isHeld(o),
  ).length;
  const checkedBlocked = operations.filter(
    (o) => checked.has(o.id) && isBlocked(o) && !isHeld(o),
  ).length;
  const checkedNear = operations.filter((o) => checked.has(o.id) && nearHeld.has(o.id));
  const checkedNoPassage = operations.filter(
    (o) => checked.has(o.id) && passageHeld.has(o.id) && !nearHeld.has(o.id),
  );
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
          {proposal.landed && (
            <Chip variant="cyan" data-testid="proposal-landed">
              landed
            </Chip>
          )}
          {inspector.gold && (
            <Chip variant={SPLIT_CHIP[inspector.gold.split]} data-testid="review-gold-split">
              {inspector.gold.split}
            </Chip>
          )}
          <ProposalOriginChip origin={proposal.origin} />
          {(proposal.links ?? [])
            .filter((link) => link.kind === "supersedes" || link.kind === "superseded_by")
            .map((link) => (
              <span
                key={`${link.kind}-${link.proposal_id}`}
                className="proposal-summary__link"
                data-testid={`proposal-supersede-${link.kind}`}
              >
                <Chip variant={link.kind === "superseded_by" ? "neutral" : "cyan"}>
                  {link.kind === "superseded_by" ? "superseded by" : "supersedes"}
                </Chip>
                <ProposalLink proposalId={link.proposal_id}>
                  {link.title || link.proposal_id.slice(0, 8)}
                </ProposalLink>
              </span>
            ))}
          {reversalChips(proposal).map(({ link, label, variant, count }) => (
            <span
              key={`${link.kind}-${link.proposal_id}`}
              className="proposal-summary__link"
              data-testid={`proposal-reversal-${link.kind}`}
            >
              <Chip variant={variant}>{label}</Chip>
              <ProposalLink proposalId={link.proposal_id}>
                {link.title || link.proposal_id.slice(0, 8)}
              </ProposalLink>
              {count && (
                <span className="proposal-summary__count" data-testid="proposal-reversal-count">
                  {count}
                </span>
              )}
            </span>
          ))}
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
          {decidesHere && progress.awaiting > 0 && <ReviewElapsed pageMs={clock.pageMs} />}
          {onCompare && (
            <CompareEntry
              proposal={proposal}
              onCompare={onCompare}
              data-testid="proposal-compare"
            />
          )}
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
              <RevertControl
                proposal={proposal}
                busy={actions.busy}
                confirming={confirmRevert}
                onConfirmingChange={setConfirmRevert}
                onRevert={() => void actions.revertProposal()}
              />
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

      {inspector.gold?.split === "holdout" && (
        <p className="review-gold-note" data-testid="review-gold-holdout">
          {HOLDOUT_NOTE}
        </p>
      )}

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

      <ReviewPillsProvider value={inspector.pills}>
        <div
          ref={panes.ref}
          className={
            sourcePane.shown ? "proposal-review proposal-review--source" : "proposal-review"
          }
          // With a source, the panes fill the window below them (measured at run time).
          style={
            sourcePane.shown && panes.height
              ? ({ "--review-panes-height": `${panes.height}px` } as CSSProperties)
              : undefined
          }
          data-testid="proposal-review"
        >
          <div
            className={["proposal-main", fold && `proposal-main--fold-${fold}`]
              .filter(Boolean)
              .join(" ")}
            data-testid="proposal-operations-list"
            data-filter={filter}
            data-group-by={groupBy}
            data-fold={fold}
          >
            {sourcePane.shown &&
              (fold === "source" ? (
                <PaneRail
                  label="Source"
                  shortcut="["
                  expandLabel="Expand the source"
                  mapLabel="Highlights in the source"
                  marks={sourcePane.rail.marks}
                  selectedPosition={sourcePane.rail.selectedPosition}
                  onExpand={() => changeFold(undefined)}
                  onMarkClick={(markId) => {
                    // The highlight clicked, not the item's first one.
                    const { operationId, start } = railMarkTarget(markId);
                    changeFold(undefined);
                    onSelectOperation(operationId);
                    sourcePane.showSpan(operationId, start);
                  }}
                  {...railHover}
                  data-testid="review-source-rail"
                />
              ) : (
                sourcePane.pane
              ))}
            {wideOpen && selectedOperation && diffField && (
              <WideDiffOverlay
                operation={selectedOperation}
                title={operationTitle(selectedOperation, context)}
                field={diffField}
                fields={wideFields}
                onField={(field) => onDiff?.(field)}
                onStep={(by) => {
                  const next = stepLongChange(shownOrder, operations, selectedOperation.id, by);
                  if (next) {
                    wideFrom.current = next.field;
                    onDiff?.(next.field, next.operationId);
                  }
                }}
                onClose={() => onDiff?.(undefined)}
              />
            )}
            {fold === "list" && (
              <PaneRail
                label="Operations"
                side="right"
                shortcut="]"
                expandLabel="Expand the list"
                mapLabel="Operations in the list"
                marks={listRailMarks}
                selectedPosition={
                  selectedIndex >= 0
                    ? selectedIndex / Math.max(1, shownOrder.length - 1)
                    : undefined
                }
                positionLabel={
                  selectedIndex >= 0 ? `${selectedIndex + 1} / ${shownOrder.length}` : undefined
                }
                onExpand={() => changeFold(undefined)}
                onMarkClick={(operationId) => {
                  changeFold(undefined);
                  onSelectOperation(operationId);
                }}
                {...railHover}
                data-testid="review-list-rail"
              />
            )}
            <ReviewElementsPane
              id="proposal-operations"
              hidden={fold === "list"}
              onFold={canFold ? () => changeFold("list") : undefined}
              title="Operations"
              listLabel="Operations to review"
              data-testid="proposal-operations"
              sections={sections}
              rowOf={rowOf}
              selectedId={selectedId}
              link={inspectorLink}
              emptyMessage={emptyMessage}
              header={
                <div data-testid="proposal-operation-filter">
                  <SegmentedControl
                    value={filter}
                    onChange={(value) => chooseFilter(value as OperationFilter)}
                    aria-label="Show operations"
                    options={[
                      { value: "needs", label: `Needs decision · ${progress.awaiting}` },
                      {
                        value: "decided",
                        label: `Decided · ${progress.total - progress.awaiting}`,
                      },
                      { value: "all", label: `All · ${operations.length}` },
                    ]}
                  />
                </div>
              }
              toolbar={
                <>
                  <div className="review-list-tools" data-testid="proposal-list-tools">
                    {groupOptions.length > 1 && (
                      <span className="proposal-group-by" data-testid="proposal-group-by">
                        <span className="proposal-bar__label">Group by</span>
                        <SegmentedControl
                          value={groupBy}
                          onChange={(value) => setGroupBy(value as ListGroupBy)}
                          aria-label="Group operations by"
                          options={groupOptions.map((value) => ({
                            value,
                            label: GROUP_BY_LABELS[value],
                          }))}
                        />
                      </span>
                    )}
                    {counts.ops.length > 1 && (
                      <div data-testid="proposal-op-filter">
                        <SegmentedControl
                          value={facets.op}
                          onChange={(value) =>
                            chooseFacets({ ...facets, op: value as Facets["op"] })
                          }
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
                          onChange={(value) =>
                            chooseFacets({ ...facets, scope: value as Facets["scope"] })
                          }
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
                    {bulk && (
                      <BulkSelect
                        ready={shownReady.length}
                        awaiting={shownBulk.length}
                        atThreshold={matching?.length}
                        threshold={threshold}
                        onThreshold={setThreshold}
                        onPick={pickBulk}
                        disabled={actions.busy}
                        leftOut={readyLeftOut && `${readyLeftOut}.`}
                      />
                    )}
                  </div>
                  {bulk && checked.size > 0 && (
                    <BulkBar
                      selected={checked.size}
                      stale={checkedStale}
                      blocked={checkedBlocked}
                      nearMatches={checkedNear}
                      noPassage={checkedNoPassage}
                      busy={actions.busy}
                      applying={actions.pending?.action === "apply"}
                      onClear={() => setChecked([])}
                      onReject={() => {
                        setRejectNote("");
                        setRejectCode("other");
                        setRejecting({ ids: checkedList });
                      }}
                      onAccept={async () => {
                        await actions.acceptFresh(checkedList);
                        setChecked([]);
                      }}
                    />
                  )}
                  {reverted && (
                    <p className="proposals-footnote review-list-note">
                      This proposal was reverted: what it applied is undone, and it takes no more
                      decisions.
                    </p>
                  )}
                </>
              }
              selection={
                bulk
                  ? {
                      checked,
                      toggle: (opId) =>
                        setChecked((ids) =>
                          ids.includes(opId) ? ids.filter((i) => i !== opId) : [...ids, opId],
                        ),
                      eligible: (operation) =>
                        isAwaiting(operation) && isBulkEligible(operation, conflicted),
                    }
                  : undefined
              }
              renderConflict={(cluster) => (
                <ConflictCard
                  cluster={cluster}
                  context={context}
                  deciding={decidesHere}
                  reverted={reverted}
                  actions={actions}
                  shown={shownIds}
                  selectedOperationId={selectedId}
                  onSelectOperation={onSelectOperation}
                />
              )}
            />
          </div>
          {selectedOperation ? (
            <ReviewInspector
              key={selectedOperation.id}
              {...inspector.inspectorProps(selectedOperation)}
              reverted={reverted}
              rejectPrompt={rejectPrompt}
              onShowPassage={
                sourcePane.shown
                  ? (quote) => {
                      // Show in source unfolds a folded source first.
                      if (fold === "source") changeFold(undefined);
                      sourcePane.showPassage(selectedOperation.id, quote);
                    }
                  : undefined
              }
              onWide={onDiff ? openWide : undefined}
              decidedBy={
                reverted
                  ? undefined
                  : decidedByLabel(
                      decisions?.find((d) => d.operation_id === selectedOperation.id)?.decided_by,
                      decisions?.find((d) => d.operation_id === selectedOperation.id)?.decided_at,
                    )
              }
              type={typeOf(selectedOperation)}
            />
          ) : (
            <p
              className="review-pane review-pane--inspector review-muted proposal-review__empty"
              data-testid="proposal-inspector-empty"
            >
              Select an operation to see its change, why it was proposed, and its evidence.
            </p>
          )}
        </div>
        {inspector.overlay.overlay}
      </ReviewPillsProvider>

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
          const done = await actions.rejectOperations(rejecting.ids, rejectNote, {
            reasonCode: rejectCode,
          });
          if (done) setChecked([]);
        }}
        title={`Reject ${rejecting?.ids.length ?? 0} selected?`}
        message={
          <div className="stack">
            <p>
              A rejected operation can&apos;t be applied later. Operations already applied stay
              applied.
            </p>
            <Field label="Because" hint="one reason for every operation">
              <RejectReasonPicker
                operations={operations.filter((o) => rejecting?.ids.includes(o.id))}
                value={rejectCode}
                onChange={setRejectCode}
              />
            </Field>
            <Field
              label="Note"
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
    </div>
  );
}
