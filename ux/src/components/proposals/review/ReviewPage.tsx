import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, ConfirmDialog, PageHeader, ProgressBar } from "@tinkermonkey/heimdall-ui";
import { SMALL_SET_LIMIT } from "@/api/config";
import { ApiError } from "@/api/client/interceptors";
import { useChangeProposal } from "@/api/hooks/proposals";
import { useTaxonomyClasses } from "@/api/hooks/ontology/useClasses";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import { useSchemes } from "@/api/hooks/ontology/useSchemes";
import { useSource, useSourceText } from "@/api/hooks/sources/useSource";
import type { ProposedOperation, RejectionReason } from "@/api/services/proposals";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useToasts } from "@/components/ui/Toast";
import { usePageBreadcrumbs } from "@/hooks/usePageBreadcrumbs";
import { linkPath } from "@/lib/entityPaths";
import { takesDecisions } from "../decisionModel";
import { formatProbability, isAwaiting, refsByOperation } from "../proposalModel";
import { ProposalOriginChip } from "../ProposalOrigin";
import { useOperationContext } from "../useOperationContext";
import { useProposalActions, type ApplyOutcome } from "../useProposalActions";
import { ReviewElementsPane, type ElementRow } from "./ReviewElementsPane";
import { ReviewInspector, type ReviewNames } from "./ReviewInspector";
import { ReviewSourcePane } from "./ReviewSourcePane";
import {
  filterGroups,
  formatDuration,
  groupForReview,
  isElement,
  isRelationship,
  nextAwaiting,
  orderOf,
  proposedClassId,
  rememberPick,
  reviewProgress,
  reviewSourceId,
  reviewSpans,
  shownClassId,
  step,
  suggestedClasses,
  verdictOf,
  type ElementFilter,
  type Layer,
} from "./reviewModel";
import { useReviewClock } from "./useReviewClock";
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

/** Keys typed into a field are text, not review commands. */
function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT"
  );
}

type Decision =
  | { kind: "correct" }
  | { kind: "class"; classId: string }
  | { kind: "reject"; reasonCode: RejectionReason; note: string };

interface ReviewPageProps {
  id: string;
  /** Back to the proposal's page. */
  onFinish: () => void;
}

/**
 * An extraction proposal reviewed against its whole source: the source with
 * every element's passages highlighted by verdict, the elements grouped by
 * layer, and the selected one in the inspector, decided by button or key
 * (A correct, 1-3 a class picked earlier, X a reason, J / K next and previous).
 * Each decision records the active time spent on the element.
 */
export function ReviewPage({ id, onFinish }: ReviewPageProps) {
  const { toast } = useToasts();
  const { data: proposal, error, refetch } = useChangeProposal(id);
  const taxonomyId = proposal?.taxonomy_id ?? "";
  const operations = useMemo(() => proposal?.operations ?? [], [proposal]);
  const refs = useMemo(() => (proposal ? refsByOperation([proposal]) : undefined), [proposal]);
  const context = useOperationContext(operations, refs);
  const actions = useProposalActions(proposal);
  const { classes } = useTaxonomyClasses(taxonomyId, !!taxonomyId);
  const { data: schemes } = useSchemes(
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
  const sourceId = useMemo(() => reviewSourceId(elements), [elements]);
  const { data: source, isError: sourceFailed } = useSource(sourceId);
  const readable = !!source && source.status === "ready" && !source.removed_at;
  const { data: sourceText, isError: textFailed } = useSourceText(sourceId, null, {
    enabled: readable,
  });
  const spans = useMemo(
    () =>
      sourceId && sourceText
        ? reviewSpans(elements, sourceId, sourceText.text, sourceText.start)
        : [],
    [elements, sourceId, sourceText],
  );

  // Classes and their layers (concept schemes).
  const classById = useMemo(() => new Map((classes ?? []).map((c) => [c.id, c])), [classes]);
  const pickable = useMemo(() => (classes ?? []).filter((c) => !c.derived), [classes]);
  const schemeById = useMemo(
    () => new Map((schemes?.items ?? []).map((s) => [s.id, s])),
    [schemes],
  );
  const layerOf = useCallback(
    (operation: ProposedOperation): Layer => {
      const scheme = schemeById.get(
        classById.get(proposedClassId(operation) ?? "")?.concept_scheme_id ?? "",
      );
      return scheme ? { key: scheme.id, label: scheme.title } : { key: "other", label: "Other" };
    },
    [classById, schemeById],
  );

  const names: ReviewNames = useMemo(() => {
    const classLabel = (classId: string | undefined) => {
      if (!classId) return "no class";
      const found = classById.get(classId);
      return found?.identifier || found?.title || classId;
    };
    const endTitle = (value: unknown, operation: ProposedOperation) =>
      typeof value === "string" ? (context.nameOf(value, operation) ?? value) : "?";
    const relationshipParts = (operation: ProposedOperation) => ({
      from: endTitle(operation.fields?.source_id, operation),
      predicate:
        context.predicateOf(operation.fields?.property_definition_id as string | undefined) ?? "…",
      to: endTitle(operation.fields?.target_id, operation),
    });
    return {
      classLabel,
      classOf: (classId) => (classId ? classById.get(classId) : undefined),
      relationshipParts,
      titleOf: (operation) => {
        if (isRelationship(operation)) {
          const { from, predicate, to } = relationshipParts(operation);
          return `${from} ${predicate} ${to}`;
        }
        const title = operation.fields?.title;
        return typeof title === "string" && title ? title : `#${operation.seq}`;
      },
    };
  }, [classById, context]);

  const rowOf = (operation: ProposedOperation): ElementRow => ({
    title: isRelationship(operation)
      ? `${names.relationshipParts(operation).from} → ${names.relationshipParts(operation).to}`
      : names.titleOf(operation),
    detail: isRelationship(operation)
      ? names.relationshipParts(operation).predicate
      : names.classLabel(shownClassId(operation)),
    probability:
      operation.probability === null || operation.probability === undefined
        ? ""
        : formatProbability(operation.probability),
    verdict: verdictOf(operation),
  });

  // Groups, filter and selection.
  const [filter, setFilter] = useState<ElementFilter>("all");
  const [chosenId, setSelectedId] = useState<string>();
  const groups = useMemo(
    () => groupForReview(elements, relationships, layerOf),
    [elements, relationships, layerOf],
  );
  const order = useMemo(() => orderOf(groups), [groups]);
  // Until the reviewer picks one, the first element awaiting a decision (else the first).
  const selectedId =
    chosenId ??
    order.find((opId) => reviewed.some((o) => o.id === opId && isAwaiting(o))) ??
    order[0];
  const shownGroups = useMemo(
    () => filterGroups(groups, filter, selectedId),
    [groups, filter, selectedId],
  );
  const shownOrder = useMemo(() => orderOf(shownGroups), [shownGroups]);
  const selected = reviewed.find((o) => o.id === selectedId);
  useEffect(() => clock.startElement(selectedId), [clock, selectedId]);

  // Classes picked earlier in this review, most recent first.
  const [recentClasses, setRecentClasses] = useState<string[]>([]);
  const suggestions = useMemo(
    () =>
      selected && isElement(selected)
        ? suggestedClasses(recentClasses, shownClassId(selected)).flatMap(
            (classId) => classById.get(classId) ?? [],
          )
        : [],
    [recentClasses, selected, classById],
  );

  const deciding = !!proposal && takesDecisions(proposal);
  const reasonsRef = useRef<HTMLDivElement>(null);

  /** After deciding `decidedId`, select the next element still awaiting a decision. */
  const advance = (decidedId: string, after: ProposedOperation[]) => {
    const awaiting = new Set(after.filter(isAwaiting).map((o) => o.id));
    awaiting.delete(decidedId);
    const next = nextAwaiting(order, awaiting, decidedId);
    if (next) setSelectedId(next);
  };

  /** The applied outcome of one operation, or why it didn't apply (the toast says so). */
  const appliedOutcome = (operation: ProposedOperation, outcome: ApplyOutcome) => {
    if (outcome.error || outcome.cancelled || !outcome.proposal) return undefined;
    const after = outcome.proposal.operations.find((o) => o.id === operation.id);
    if (after?.status === "failed") {
      toast("error", "Apply failed", after.reason ?? "The server gave no reason.");
      return undefined;
    }
    return outcome.proposal.operations;
  };

  const decide = async (operation: ProposedOperation, decision: Decision) => {
    if (!deciding || !isAwaiting(operation) || actions.busy) return;
    const reviewMs = { [operation.id]: clock.spentOn(operation.id) };
    if (decision.kind === "reject") {
      const rejected = await actions.rejectOperations([operation.id], decision.note, {
        reasonCode: decision.reasonCode,
        reviewMs,
      });
      if (rejected) advance(operation.id, operations);
      return;
    }
    const outcome = await actions.accept([operation.id], {
      reviewMs,
      edits:
        decision.kind === "class"
          ? { [operation.id]: { class_ids: [decision.classId] } }
          : undefined,
    });
    const after = appliedOutcome(operation, outcome);
    if (!after) return;
    if (decision.kind === "class") {
      setRecentClasses((recent) => rememberPick(recent, decision.classId));
    }
    advance(operation.id, after);
  };

  // Keys: A correct, 1-3 a suggested class, X the reasons, J / K next and previous.
  const onKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onKey.current = (event) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    if (isTyping(event.target)) return;
    const key = event.key.toLowerCase();
    if (key === "j" || key === "k") {
      const next = step(shownOrder, selectedId, key === "j" ? 1 : -1);
      if (next) setSelectedId(next);
      event.preventDefault();
      return;
    }
    if (!selected || !deciding || !isAwaiting(selected)) return;
    if (key === "a") {
      event.preventDefault();
      void decide(selected, { kind: "correct" });
    } else if (key === "x") {
      event.preventDefault();
      reasonsRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    } else if (["1", "2", "3"].includes(key) && isElement(selected)) {
      const suggestion = suggestions[Number(key) - 1];
      if (!suggestion) return;
      event.preventDefault();
      void decide(selected, { kind: "class", classId: suggestion.id });
    }
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKey.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

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
        title={`Review extraction: ${sourceTitle}`}
        actions={
          <Button variant="primary" size="sm" onClick={onFinish} data-testid="review-finish">
            Finish review
          </Button>
        }
        data-testid="review-header"
      />
      <div className="review-origin" data-testid="review-origin-line">
        <span>Proposed by</span>
        {proposal.origin ? (
          <ProposalOriginChip origin={proposal.origin} />
        ) : (
          <span className="review-mono">{proposal.source_detail || proposal.source}</span>
        )}
      </div>

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
          {progress.correct} correct · {progress.changed} class changed · {progress.rejected} not
          elements · {progress.added} added
        </span>
        <ReviewElapsed pageMs={clock.pageMs} />
      </section>

      <div className="review-panes" data-testid="review-panes">
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
        />
        <ReviewElementsPane
          groups={shownGroups}
          filter={filter}
          onFilter={setFilter}
          awaiting={awaitingCount}
          total={progress.total}
          rowOf={rowOf}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        {selected ? (
          <ReviewInspector
            key={selected.id}
            operation={selected}
            operations={operations}
            names={names}
            pickable={pickable}
            suggestions={suggestions}
            deciding={deciding}
            busy={actions.busy}
            reasonsRef={reasonsRef}
            onCorrect={() => void decide(selected, { kind: "correct" })}
            onPickClass={(classId) => void decide(selected, { kind: "class", classId })}
            onReject={(reasonCode, note) =>
              void decide(selected, { kind: "reject", reasonCode, note })
            }
            onSelect={setSelectedId}
          />
        ) : (
          <p className="review-pane review-pane--inspector review-muted">
            This proposal has no elements to review.
          </p>
        )}
      </div>

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
