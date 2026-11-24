import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import {
  Button,
  Chip,
  ConfirmDialog,
  PageHeader,
  ProgressBar,
  SegmentedControl,
} from "@tinkermonkey/heimdall-ui";
import { SMALL_SET_LIMIT } from "@/api/config";
import { ApiError } from "@/api/client/interceptors";
import { useAddProposalIndividual, useChangeProposal } from "@/api/hooks/proposals";
import { useTaxonomyClasses } from "@/api/hooks/ontology/useClasses";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useSource, useSourceText } from "@/api/hooks/sources/useSource";
import type { ProposedOperation } from "@/api/services/proposals";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { linkPath } from "@/lib/entityPaths";
import { formatProbability, isAwaiting, refsByOperation } from "../proposalModel";
import { ProposalOriginChip } from "../ProposalOrigin";
import { useOperationContext } from "../useOperationContext";
import { useProposalActions } from "../useProposalActions";
import { ReviewElementsPane, type ElementRow } from "./ReviewElementsPane";
import { rowStatus } from "./reviewList";
import { ReviewInspector } from "./ReviewInspector";
import { ReviewPillsProvider, plainClick, type OperationLink } from "./ReviewPills";
import { CompareEntry } from "../compare/CompareEntry";
import { ReviewSourcePane, type PopoverAnchor } from "./ReviewSourcePane";
import { AddElementPopover } from "./AddElementPopover";
import {
  addErrorMessage,
  addedOperation,
  additionsBlocked,
  proposalSourceId,
  toSourcePassage,
  type SelectedPassage,
} from "./addFromText";
import {
  filterGroups,
  formatDuration,
  groupForReview,
  isElement,
  isRelationship,
  nextAwaiting,
  orderOf,
  proposedClassId,
  reviewProgress,
  reviewSourceId,
  reviewSpans,
  shownClassId,
  verdictOf,
  type ElementFilter,
  type Layer,
} from "./reviewModel";
import { useReviewClock } from "./useReviewClock";
import { useReviewKeys } from "./useReviewKeys";
import { useInspectorModel } from "./useInspectorModel";
import { HOLDOUT_NOTE, SPLIT_CHIP, type Tier } from "./goldModel";
import "../proposals.css";
import "./review.css";

/** The active time on this review, ticking each second. */
function ReviewElapsed({ pageMs }: { pageMs: () => number }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => tick((n) => n + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <span className="review-progress__time" data-testid="review-time">
      {formatDuration(pageMs())} on this review
    </span>
  );
}

/** Space left under the panes at the bottom of the window. */
const PANES_BOTTOM_GAP = 24;
/** The panes never get shorter than this, however little of the window is left. */
const PANES_MIN_HEIGHT = 480;

/**
 * The height that makes the panes fill the window below where they start,
 * worked out when the page lays out and whenever the window resizes.
 */
function usePanesHeight(ready: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>();
  useLayoutEffect(() => {
    const measure = () => {
      const panes = ref.current;
      if (!panes) return;
      const rect = panes.getBoundingClientRect();
      // In the shell's scrolling canvas: fill what it shows, counting from the top of its
      // content (a scrolled page measures the same) and leaving room for whatever sits
      // below the panes (its padding), so the page never scrolls and clips the headers.
      const scroller = panes.closest("main");
      if (scroller && scroller.clientHeight > 0) {
        const box = scroller.getBoundingClientRect();
        const top = rect.top - box.top + scroller.scrollTop;
        const below = scroller.scrollHeight - (rect.bottom - box.top + scroller.scrollTop);
        setHeight(
          Math.max(PANES_MIN_HEIGHT, Math.floor(scroller.clientHeight - top - Math.max(0, below))),
        );
        return;
      }
      setHeight(
        Math.max(PANES_MIN_HEIGHT, Math.round(window.innerHeight - rect.top - PANES_BOTTOM_GAP)),
      );
    };
    measure();
    window.addEventListener("resize", measure);
    // The header above can grow (a long source title wraps once it loads).
    const page = ref.current?.parentElement;
    const observer =
      page && typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : undefined;
    if (page) observer?.observe(page);
    return () => {
      window.removeEventListener("resize", measure);
      observer?.disconnect();
    };
  }, [ready]);
  return { ref, height };
}

interface ReviewPageProps {
  id: string;
  /** Back to the proposal's page. */
  onFinish: () => void;
  /**
   * The selected operation, from the URL; with onSelect and hrefOf the page
   * follows the route (each selection a history entry). Without them it keeps
   * the selection itself.
   */
  selectedId?: string;
  onSelect?: (operationId: string) => void;
  /** The href that opens an operation (a link can open it in a new tab). */
  hrefOf?: (operationId: string) => string;
  /** Open the comparison with another open proposal for the same source. */
  onCompare?: (otherId: string) => void;
}

/**
 * An extraction proposal reviewed against its whole source: the source with
 * every element's passages highlighted by verdict, the elements grouped by
 * layer, and the selected one in the inspector, decided by button or key
 * (A correct, 1-3 a class picked earlier, X a reason, J / K next and previous;
 * on a relationship whose end was rejected, X rejects it too). Rejecting an
 * element offers to reject the awaiting relationships that use it.
 * Each decision records the active time spent on the element.
 */
export function ReviewPage({
  id,
  onFinish,
  selectedId: routeSelectedId,
  onSelect: routeOnSelect,
  hrefOf: routeHrefOf,
  onCompare,
}: ReviewPageProps) {
  const { toast } = useToasts();
  const { data: proposal, error, refetch } = useChangeProposal(id);
  const taxonomyId = proposal?.taxonomy_id ?? "";
  const operations = useMemo(() => proposal?.operations ?? [], [proposal]);
  const refs = useMemo(() => (proposal ? refsByOperation([proposal]) : undefined), [proposal]);
  const context = useOperationContext(operations, refs);
  const actions = useProposalActions(proposal);
  const { classes, isError: classesFailed } = useTaxonomyClasses(taxonomyId, !!taxonomyId);
  const { data: schemes, isError: schemesFailed } = useSchemes(
    taxonomyId,
    { limit: SMALL_SET_LIMIT },
    { enabled: !!taxonomyId },
  );
  const { data: datasets } = useDatasets(taxonomyId || undefined);
  const clock = useReviewClock();

  const elements = useMemo(() => operations.filter(isElement), [operations]);
  const relationships = useMemo(() => operations.filter(isRelationship), [operations]);
  const reviewed = useMemo(() => [...elements, ...relationships], [elements, relationships]);

  // The source: its whole text, once it is ready.
  // The source the proposal records it was extracted from, else the one its passages cite.
  const recordedSourceId = proposalSourceId(proposal);
  const citedSourceId = useMemo(() => reviewSourceId(elements), [elements]);
  const sourceId = recordedSourceId ?? citedSourceId;
  const { data: source, isError: sourceFailed } = useSource(sourceId);
  const readable = !!source && source.status === "ready" && !source.removed_at;
  const { data: sourceText, isError: textFailed } = useSourceText(sourceId, null, {
    enabled: readable,
  });
  // The highlighted passages: every element's, and the open relationship's (see below).
  const elementSpans = useMemo(
    () =>
      sourceId && sourceText
        ? reviewSpans(elements, sourceId, sourceText.text, sourceText.start)
        : [],
    [elements, sourceId, sourceText],
  );

  // Classes and their layers (concept schemes).
  const classById = useMemo(() => new Map((classes ?? []).map((c) => [c.id, c])), [classes]);
  const schemeById = useMemo(
    () => new Map((schemes?.items ?? []).map((s) => [s.id, s])),
    [schemes],
  );
  // Until the classes load, no class can be named, defined or picked (a failure falls back to ids).
  const classesLoading = !classes && !classesFailed;
  const layersLoading = classesLoading || (!schemes && !schemesFailed);
  const layerOf = useCallback(
    (operation: ProposedOperation): Layer => {
      if (layersLoading) return { key: "loading", label: "Loading layers…" };
      const scheme = schemeById.get(
        classById.get(proposedClassId(operation) ?? "")?.concept_scheme_id ?? "",
      );
      return scheme ? { key: scheme.id, label: scheme.title } : { key: "other", label: "Other" };
    },
    [classById, schemeById, layersLoading],
  );

  // Groups, filter and selection. The selection follows the route when it has one
  // (?selected=..., each selection a history entry), else the page keeps it.
  const [filter, setFilter] = useState<ElementFilter>("all");
  const [ownSelectedId, setOwnSelectedId] = useState<string>();
  const chosenId = routeOnSelect ? routeSelectedId : ownSelectedId;
  const selectedRef = useRef<string | undefined>(undefined);
  const setSelectedId = (operationId: string) => {
    // Selecting what is already selected adds no history entry.
    if (operationId === selectedRef.current) return;
    if (routeOnSelect) routeOnSelect(operationId);
    else setOwnSelectedId(operationId);
  };
  const hrefOf =
    routeHrefOf ?? ((operationId: string) => `?selected=${encodeURIComponent(operationId)}`);
  /** An operation's link: a real href (open in a new tab), a plain click selecting it here. */
  const link = (operationId: string): OperationLink => ({
    href: hrefOf(operationId),
    onClick: (event) => {
      if (!plainClick(event)) return;
      event.preventDefault();
      setSelectedId(operationId);
    },
  });
  const groups = useMemo(
    () => groupForReview(elements, relationships, layerOf),
    [elements, relationships, layerOf],
  );
  const order = useMemo(() => orderOf(groups), [groups]);
  // Until the reviewer picks one (or when a link names none of this proposal's),
  // the first element awaiting a decision, else the first.
  const selectedId =
    (chosenId && reviewed.some((o) => o.id === chosenId) ? chosenId : undefined) ??
    order.find((opId) => reviewed.some((o) => o.id === opId && isAwaiting(o))) ??
    order[0];
  selectedRef.current = selectedId;
  const shownGroups = useMemo(
    () => filterGroups(groups, filter, selectedId),
    [groups, filter, selectedId],
  );
  const shownOrder = useMemo(() => orderOf(shownGroups), [shownGroups]);
  const selected = reviewed.find((o) => o.id === selectedId);
  // A relationship's passages are highlighted while it is open: selecting it scrolls to them.
  const spans = useMemo(
    () =>
      selected && isRelationship(selected) && sourceId && sourceText
        ? [...elementSpans, ...reviewSpans([selected], sourceId, sourceText.text, sourceText.start)]
        : elementSpans,
    [elementSpans, selected, sourceId, sourceText],
  );
  useEffect(() => clock.startElement(selectedId), [clock, selectedId]);

  // The inspector's data: classes, schema, names, ends, gold, and the decision itself.
  const model = useInspectorModel(proposal, {
    actions,
    context,
    selected,
    link,
    clock,
    onDecided: (decidedId, after) => {
      // After deciding, select the next element still awaiting a decision.
      const awaiting = new Set(after.filter(isAwaiting).map((o) => o.id));
      awaiting.delete(decidedId);
      const next = nextAwaiting(order, awaiting, decidedId);
      if (next) setSelectedId(next);
    },
  });
  const { pickable, names, gold, recentClasses, rememberClass } = model;

  const rowOf = (operation: ProposedOperation): ElementRow => {
    const detail = isRelationship(operation)
      ? names.relationshipParts(operation).predicate
      : names.classLabel(shownClassId(operation));
    return {
      title: isRelationship(operation)
        ? `${names.relationshipParts(operation).from} → ${names.relationshipParts(operation).to}`
        : names.titleOf(operation),
      detail,
      detailTitle: detail,
      probability:
        operation.probability === null || operation.probability === undefined
          ? ""
          : formatProbability(operation.probability),
      ...rowStatus(operation),
      amended: !!operation.amended_at,
    };
  };

  // A passage asked for from the inspector's evidence: shown and flashed in the source.
  const [focus, setFocus] = useState<{ start: number; nonce: number }>();
  const showPassage = (operationId: string, quote: string) => {
    const span = spans.find((s) => s.key === operationId && s.quote === quote);
    if (span?.start != null) setFocus({ start: span.start, nonce: Date.now() });
  };

  // Adding an element the extraction missed, from text selected in the source.
  const addIndividual = useAddProposalIndividual();
  const [adding, setAdding] = useState<{ passage: SelectedPassage; anchor: PopoverAnchor }>();
  const [addError, setAddError] = useState<string>();
  const addBlocked = proposal ? additionsBlocked(proposal) : undefined;
  const canAdd = !!proposal && !addBlocked && !!sourceText && sourceId === recordedSourceId;
  const openAdding = (passage: SelectedPassage, anchor: PopoverAnchor) => {
    setAdding({ passage, anchor });
    setAddError(undefined);
    clock.startAdding();
  };
  const sourceTextRef = useRef<HTMLDivElement>(null);
  /** Close the add form; focus goes back to the source text unless the reviewer clicked away. */
  const closeAdding = ({ refocus = true } = {}) => {
    setAdding(undefined);
    setAddError(undefined);
    if (refocus) sourceTextRef.current?.focus({ preventScroll: true });
  };
  const addElement = async (title: string, classId: string, tier?: Tier) => {
    if (!adding || !recordedSourceId || !sourceText || addIndividual.isPending) return;
    // The server counts offsets in code points, the browser in UTF-16 units.
    const passage = toSourcePassage(adding.passage, sourceText.text, sourceText.start);
    const before = new Set(operations.map((o) => o.id));
    try {
      const after = await addIndividual.mutateAsync({
        id,
        data: {
          title,
          class_ids: [classId],
          passage: {
            source_id: recordedSourceId,
            start: passage.start,
            end: passage.end,
            quote: passage.quote,
          },
          review_ms: clock.spentAdding(),
          ...(tier ? { annotation: { tier } } : {}),
        },
      });
      closeAdding();
      window.getSelection()?.removeAllRanges();
      rememberClass(classId);
      const added = addedOperation(before, after);
      if (added) setSelectedId(added.id);
      if (added?.status === "failed") {
        toast("error", `Added ${title}, but it didn't apply`, added.reason ?? undefined);
      } else {
        toast("success", `Added ${title}`, `As ${names.classLabel(classId)}`);
      }
    } catch (error) {
      setAddError(addErrorMessage(error, { title, classLabel: names.classLabel(classId) }));
    }
  };
  // Key X opens the selected operation's reason step: each press bumps this.
  const [rejectPrompt, setRejectPrompt] = useState(0);

  // Keys: A correct, 1-3 a suggested class, X the reasons, J / K next and previous.
  // While the add form is open, keys are its own; Escape closes it wherever focus went.
  useReviewKeys({
    order: shownOrder,
    selectedId,
    select: setSelectedId,
    selected,
    operations,
    model,
    paused: !!adding || !!actions.forceRequest,
    onReasons: () => setRejectPrompt((n) => n + 1),
  });
  const onAddingKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onAddingKey.current = (event) => {
    if (adding && event.key === "Escape" && !event.defaultPrevented) closeAdding();
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onAddingKey.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  const panes = usePanesHeight(!!proposal);

  usePageBreadcrumbs(
    `${linkPath("proposal", id)}/review`,
    proposal
      ? [
          { label: "Proposals", to: "/app/proposals" },
          { label: proposal.title, to: linkPath("proposal", id) },
          { label: "Review" },
        ]
      : null,
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
      <div className="review-page" data-testid="review-page">
        <div className="skeleton entity-page__skeleton" aria-busy="true" />
      </div>
    );
  }

  const progress = reviewProgress(reviewed);
  const awaitingCount = progress.total - progress.decided;
  const dataset = datasets?.find((d) => d.id === proposal.dataset_id);
  const sourceTitle = source?.title ?? "source";
  const eyebrow = [
    "PROPOSAL",
    source && `SOURCE ${source.title}`,
    dataset && `DATASET ${dataset.identifier || dataset.title}`,
  ]
    .filter(Boolean)
    .join(" · ");
  const unavailable = !sourceId
    ? "No element cites a passage in a source."
    : sourceFailed
      ? "The source couldn't be loaded."
      : source?.removed_at
        ? "The source was removed; its passages stay in each element's evidence."
        : source && source.status !== "ready"
          ? `The source isn't ready (${source.status}).`
          : textFailed
            ? "The source's text couldn't be loaded."
            : undefined;
  const force = actions.forceRequest;

  return (
    <div className="review-page" data-testid="review-page">
      <PageHeader
        eyebrow={eyebrow}
        title={gold ? `Gold check: ${gold.document}` : `Review extraction: ${sourceTitle}`}
        actions={
          <span className="review-header-actions">
            {onCompare && (
              <CompareEntry
                proposal={proposal}
                onCompare={onCompare}
                data-testid="review-compare"
              />
            )}
            <Button variant="primary" size="sm" onClick={onFinish} data-testid="review-finish">
              Finish review
            </Button>
          </span>
        }
        data-testid="review-header"
      />
      <div className="review-origin" data-testid="review-origin-line">
        {gold && (
          <Chip variant={SPLIT_CHIP[gold.split]} data-testid="review-gold-split">
            {gold.split}
          </Chip>
        )}
        <span>Proposed by</span>
        {proposal.origin ? (
          <ProposalOriginChip origin={proposal.origin} />
        ) : (
          <span className="review-mono">{proposal.source_detail || proposal.source}</span>
        )}
      </div>

      {gold?.split === "holdout" && (
        <p className="review-gold-note" data-testid="review-gold-holdout">
          {HOLDOUT_NOTE}
        </p>
      )}

      <section
        className="review-progress"
        aria-label="Decision progress"
        aria-busy={actions.pending ? true : undefined}
        data-testid="review-progress"
      >
        <span className="review-eyebrow">Decided</span>
        <span className="review-progress__decided" data-testid="review-progress-decided">
          {progress.decided} / {progress.total}
        </span>
        <div className="review-progress__bar">
          <ProgressBar
            percent={progress.percent}
            color={awaitingCount > 0 ? "amber" : "emerald"}
            height={6}
            label={`${progress.decided} of ${progress.total} decided`}
            data-testid="review-progress-bar"
          />
        </div>
        <span className="review-progress__counts" data-testid="review-progress-counts">
          {progress.correct} correct · {progress.changed} changed · {progress.rejected} rejected ·{" "}
          {progress.added} added
        </span>
        <ReviewElapsed pageMs={clock.pageMs} />
      </section>

      <ReviewPillsProvider value={model.pills}>
        <div
          ref={panes.ref}
          className="review-panes"
          // The window height left below the panes' top: worked out at run time.
          style={
            panes.height
              ? ({ "--review-panes-height": `${panes.height}px` } as CSSProperties)
              : undefined
          }
          data-testid="review-panes"
        >
          <ReviewSourcePane
            title={source?.title}
            text={sourceText?.text}
            unavailable={unavailable}
            spans={spans}
            verdictOf={(opId) => {
              const operation = reviewed.find((o) => o.id === opId);
              return operation ? verdictOf(operation) : "awaiting";
            }}
            titleOf={(opId) => {
              const operation = reviewed.find((o) => o.id === opId);
              return operation ? names.titleOf(operation) : opId;
            }}
            selectedId={selectedId}
            onSelect={setSelectedId}
            focus={focus}
            textRef={sourceTextRef}
            onDismissPopover={() => closeAdding({ refocus: false })}
            onSelectText={canAdd ? openAdding : undefined}
            addBlocked={addBlocked}
            popoverAnchor={adding?.anchor}
            popover={
              adding && (
                <AddElementPopover
                  key={`${adding.passage.start}-${adding.passage.end}`}
                  passage={adding.passage}
                  pickable={pickable}
                  classesLoading={classesLoading}
                  initialClassId={recentClasses[0]}
                  classLabel={names.classLabel}
                  classOf={names.classOf}
                  busy={addIndividual.isPending}
                  error={addError}
                  onEdit={() => setAddError(undefined)}
                  askTier={!!gold}
                  onAdd={(title, classId, tier) => void addElement(title, classId, tier)}
                  onCancel={() => closeAdding()}
                />
              )
            }
          />
          <ReviewElementsPane
            sections={shownGroups.map((g) => ({
              key: g.key,
              label: g.label,
              items: g.operations.map((operation) => ({ type: "row" as const, operation })),
            }))}
            header={
              <div data-testid="review-filter">
                <SegmentedControl
                  value={filter}
                  onChange={(value) => setFilter(value as ElementFilter)}
                  aria-label="Show elements"
                  options={[
                    { value: "awaiting", label: `Awaiting · ${awaitingCount}` },
                    { value: "all", label: `All · ${progress.total}` },
                  ]}
                />
              </div>
            }
            emptyMessage={
              filter === "awaiting" ? "Nothing awaits a decision." : "Nothing to review."
            }
            rowOf={rowOf}
            selectedId={selectedId}
            link={link}
          />
          {selected ? (
            <ReviewInspector
              key={selected.id}
              {...model.inspectorProps(selected)}
              rejectPrompt={rejectPrompt}
              onShowPassage={(quote) => showPassage(selected.id, quote)}
            />
          ) : (
            <p className="review-pane review-pane--inspector review-muted">
              This proposal has no elements to review.
            </p>
          )}
        </div>
        {model.overlay.overlay}
      </ReviewPillsProvider>

      <ConfirmDialog
        isOpen={!!force}
        onClose={actions.cancelForce}
        onConfirm={actions.confirmForce}
        title="Apply anyway?"
        message={
          <span data-testid="review-force-message">
            This element&apos;s target changed after it was proposed. Applying keeps the proposed
            values over those changes.
          </span>
        }
        confirmLabel="Apply anyway"
        variant="primary"
      />
    </div>
  );
}
