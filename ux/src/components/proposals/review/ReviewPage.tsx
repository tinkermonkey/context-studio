import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
} from "react";
import { Button, Chip, ConfirmDialog, PageHeader, ProgressBar } from "@tinkermonkey/heimdall-ui";
import { SCHEMA_PROPERTIES_LIMIT, SMALL_SET_LIMIT } from "@/api/config";
import { ApiError } from "@/api/client/interceptors";
import { useAddProposalIndividual, useChangeProposal } from "@/api/hooks/proposals";
import { useTaxonomyClasses } from "@/api/hooks/ontology/useClasses";
import { useDatasets } from "@/api/hooks/ontology/useDatasets";
import { useIndividuals, useIndividualsByIds } from "@/api/hooks/ontology/useIndividuals";
import { useTaxonomyPredicates } from "@/api/hooks/ontology/usePredicates";
import { useProperties } from "@/api/hooks/ontology/useProperties";
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
import {
  chosenAlternative,
  defaultNearMatchChoice,
  isNearMatch,
  type NearMatchChoice,
} from "../sourceModel";
import { useOperationContext } from "../useOperationContext";
import { useProposalActions, type ApplyOutcome } from "../useProposalActions";
import { useHoverOverlay } from "../HoverOverlay";
import { ReviewElementsPane, type ElementRow } from "./ReviewElementsPane";
import { ReviewInspector, type ReviewNames } from "./ReviewInspector";
import { ReviewPillsProvider, type OperationLink, type ReviewPillsValue } from "./ReviewPills";
import type { EndCandidate, EndInfo } from "./ReviewRelationship";
import { buildReviewSchema } from "./reviewSchema";
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
  endOperation,
  endsToDecide,
  filterGroups,
  forgetPick,
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
  shownFields,
  shownTitle,
  step,
  suggestedClasses,
  verdictLabel,
  verdictOf,
  type ElementFilter,
  type Layer,
} from "./reviewModel";
import { useReviewClock } from "./useReviewClock";
import {
  EMPTY_DRAFT,
  HOLDOUT_NOTE,
  SPLIT_CHIP,
  annotationOf,
  classesByRef,
  goldCheckOf,
  goldElementOf,
  goldTierOf,
  type GoldDraft,
  type Tier,
} from "./goldModel";
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

/** Keys typed into a field, or pressed in a dialog, are not review commands. */
function ignoresKeys(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target.isContentEditable ||
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.tagName === "SELECT" ||
    !!target.closest('[role="dialog"]')
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
      const top = ref.current?.getBoundingClientRect().top;
      if (top === undefined) return;
      setHeight(
        Math.max(PANES_MIN_HEIGHT, Math.round(window.innerHeight - top - PANES_BOTTOM_GAP)),
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

type Decision =
  | { kind: "correct" }
  | { kind: "class"; classId: string }
  | { kind: "edit"; edit: Record<string, string> }
  | { kind: "reject"; reasonCode: RejectionReason; note: string };

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
}

/** A plain left click selects in place; a modified one is left to the browser (new tab). */
function plainClick(event: MouseEvent): boolean {
  return !(event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0);
}

/**
 * An extraction proposal reviewed against its whole source: the source with
 * every element's passages highlighted by verdict, the elements grouped by
 * layer, and the selected one in the inspector, decided by button or key
 * (A correct, 1-3 a class picked earlier, X a reason, J / K next and previous).
 * Each decision records the active time spent on the element.
 */
export function ReviewPage({
  id,
  onFinish,
  selectedId: routeSelectedId,
  onSelect: routeOnSelect,
  hrefOf: routeHrefOf,
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
  const pickable = useMemo(() => (classes ?? []).filter((c) => !c.derived), [classes]);
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

  // The schema: every relationship type, with the taxonomy's predicate catalog.
  const { data: propertyList, isError: propertiesFailed } = useProperties(
    undefined,
    { limit: SCHEMA_PROPERTIES_LIMIT },
    { enabled: !!taxonomyId },
  );
  const { data: catalog } = useTaxonomyPredicates(taxonomyId || undefined);
  const schema = useMemo(
    () =>
      buildReviewSchema({
        classes: classes ?? [],
        schemes: schemes?.items ?? [],
        properties: propertyList?.items ?? [],
        predicates: catalog ?? [],
        loading: classesLoading || (!propertyList && !propertiesFailed),
      }),
    [classes, schemes, propertyList, catalog, classesLoading, propertiesFailed],
  );

  // Individuals a relationship names by id (an existing end, or an edit's): titles and classes.
  const endIds = useMemo(
    () =>
      relationships.flatMap((o) =>
        [shownFields(o).source_id, shownFields(o).target_id].filter(
          (v): v is string => typeof v === "string" && !v.startsWith("$"),
        ),
      ),
    [relationships],
  );
  const { data: endIndividuals } = useIndividualsByIds(endIds);

  const names: ReviewNames = useMemo(() => {
    const labelOf = (classId: string | undefined) => {
      if (classesLoading) return classId ? "…" : "no class";
      return schema.classLabel(classId);
    };
    const created = (value: unknown) => endOperation(value, operations);
    const endTitle = (value: unknown, operation: ProposedOperation) => {
      const create = created(value);
      if (create) return shownTitle(create);
      const found = endIndividuals?.items.find((i) => i.id === value);
      if (found) return found.title;
      return typeof value === "string" ? (context.nameOf(value, operation) ?? value) : "?";
    };
    const relationshipParts = (operation: ProposedOperation) => {
      const fields = shownFields(operation);
      const propertyId = fields.property_definition_id as string | undefined;
      return {
        from: endTitle(fields.source_id, operation),
        predicate: schema.property(propertyId)
          ? schema.predicateLabel(propertyId)
          : (context.predicateOf(propertyId) ?? "…"),
        to: endTitle(fields.target_id, operation),
      };
    };
    return {
      classLabel: labelOf,
      classOf: (classId) => (classId ? classById.get(classId) : undefined),
      relationshipParts,
      titleOf: (operation) => {
        if (isRelationship(operation)) {
          const { from, predicate, to } = relationshipParts(operation);
          return `${from} ${predicate} ${to}`;
        }
        return shownTitle(operation);
      },
    };
  }, [classById, context, classesLoading, schema, operations, endIndividuals]);

  /** A relationship's end as the inspector shows it: an element of the proposal, or an individual. */
  const endOf = (value: unknown): EndInfo => {
    const create = endOperation(value, operations);
    if (create) {
      return {
        title: shownTitle(create),
        classId: shownClassId(create),
        verdict: verdictOf(create),
        status: verdictLabel(create),
        operationId: create.id,
      };
    }
    const found = endIndividuals?.items.find((i) => i.id === value);
    return {
      title: found?.title ?? (typeof value === "string" ? value : "?"),
      classId: found?.class_ids?.[0],
      status: found ? "in the workspace" : "not found",
    };
  };

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
    verdictLabel: verdictLabel(operation),
  });

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

  // Gold mode: a benchmark gold file loaded for a person to check.
  const gold = useMemo(() => goldCheckOf(proposal), [proposal]);
  // What the reviewer has noted for gold, by operation (tier, also defensible, keep old class).
  const [goldDrafts, setGoldDrafts] = useState<Record<string, GoldDraft>>({});
  const draftOf = (operation: ProposedOperation) => goldDrafts[operation.id] ?? EMPTY_DRAFT;
  /** The gold annotation a decision on `operation` sends, if anything was noted. */
  const goldAnnotations = (operation: ProposedOperation, newClassId?: string) => {
    if (!gold) return undefined;
    const annotation = annotationOf(draftOf(operation), {
      goldTier: goldTierOf(gold, operation),
      oldClassId: shownClassId(operation),
      newClassId,
    });
    return annotation ? { [operation.id]: annotation } : undefined;
  };

  // Classes picked earlier in this review, most recent first; in gold mode the
  // element's acceptable classes come first.
  const [recentClasses, setRecentClasses] = useState<string[]>([]);
  const suggestions = useMemo(() => {
    if (!selected || !isElement(selected)) return [];
    const current = shownClassId(selected);
    const goldEntry = gold ? goldElementOf(gold, selected) : undefined;
    const acceptable = goldEntry
      ? classesByRef(goldEntry.acceptableClasses, classes ?? []).filter((c) => c.id !== current)
      : [];
    const recent = suggestedClasses(recentClasses, current).flatMap(
      (classId) => classById.get(classId) ?? [],
    );
    const all = [...acceptable, ...recent].filter(
      (c, i, list) => list.findIndex((x) => x.id === c.id) === i,
    );
    return all.slice(0, Math.max(3, acceptable.length));
  }, [recentClasses, selected, classById, classes, gold]);

  // The individuals a relationship's ends can be changed to: this proposal's accepted
  // elements, and the dataset's individuals (loaded once a relationship is open).
  const relationshipOpen = !!selected && isRelationship(selected);
  const { data: datasetIndividuals } = useIndividuals(
    { dataset_id: proposal?.dataset_id ?? undefined, limit: SMALL_SET_LIMIT, sort_by: "title" },
    { enabled: relationshipOpen && !!proposal?.dataset_id },
  );
  const endCandidates = useMemo((): EndCandidate[] => {
    if (!relationshipOpen) return [];
    const accepted = elements
      .filter((o) => o.status === "applied" && o.result_entity_id)
      .map((o) => ({
        entityId: o.result_entity_id!,
        title: shownTitle(o),
        classId: shownClassId(o),
        operationId: o.id,
      }));
    const known = new Set(accepted.map((c) => c.entityId));
    const others = (datasetIndividuals?.items ?? [])
      .filter((i) => !known.has(i.id))
      .map((i) => ({ entityId: i.id, title: i.title, classId: i.class_ids?.[0] }));
    return [...accepted, ...others];
  }, [relationshipOpen, elements, datasetIndividuals]);

  // The hover overlay the pills share, beside the inspector.
  const overlay = useHoverOverlay("#review-inspector");
  const pills: ReviewPillsValue = { schema, overlay, link };

  // A passage asked for from the inspector's evidence: shown and flashed in the source.
  const [focus, setFocus] = useState<{ start: number; nonce: number }>();
  const showPassage = (operationId: string, quote: string) => {
    const span = spans.find((s) => s.key === operationId && s.quote === quote);
    if (span?.start != null) setFocus({ start: span.start, nonce: Date.now() });
  };

  const deciding = !!proposal && takesDecisions(proposal);

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
      setRecentClasses((recent) => rememberPick(recent, classId));
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
  const reasonsRef = useRef<HTMLDivElement>(null);

  // A near match's choice, by operation: an existing individual, or create new.
  const [nearChoices, setNearChoices] = useState<Record<string, NearMatchChoice>>({});
  const nearChoiceOf = (operation: ProposedOperation) =>
    nearChoices[operation.id] ?? defaultNearMatchChoice(operation);
  /** The existing individual a near match is accepted as; undefined to create it. */
  const existingOf = (operation: ProposedOperation) =>
    isElement(operation) && isNearMatch(operation)
      ? chosenAlternative(nearChoiceOf(operation))
      : undefined;
  /**
   * A relationship can't be accepted before its new ends are, nor after one is
   * rejected; an end the edit replaces doesn't count.
   */
  const acceptBlocked = (
    operation: ProposedOperation,
    all: ProposedOperation[],
    edit?: Record<string, string>,
  ) => {
    const ends = endsToDecide(operation, all);
    const kept = (end: { role: "source" | "target" }) => !edit?.[`${end.role}_id`];
    return ends.undecided.some(kept) || ends.rejected.some(kept);
  };

  /**
   * Reopen a decided operation so it can be decided again: the operation as
   * reopened and the proposal's operations then, or undefined when refused.
   * Accepted relationships that use it reopen with it; the toast says so.
   */
  const reopen = async (operation: ProposedOperation) => {
    const after = await actions.reopenOperations([operation.id]);
    if (!after) return undefined;
    const reopened = after.operations.find((o) => o.id === operation.id);
    if (!reopened) return undefined;
    const withIt = after.operations.filter(
      (o) =>
        o.id !== operation.id &&
        isAwaiting(o) &&
        operations.some((before) => before.id === o.id && !isAwaiting(before)),
    );
    if (withIt.length > 0) {
      toast(
        "info",
        `${withIt.length} relationship${withIt.length === 1 ? " awaits" : "s await"} a decision again`,
        `They used ${shownTitle(operation)}: ${withIt.map((o) => `#${o.seq}`).join(", ")}`,
      );
    }
    return { operation: reopened, operations: after.operations };
  };

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

  const decide = async (decided: ProposedOperation, decision: Decision) => {
    if (!deciding || actions.busy) return;
    const edit = decision.kind === "edit" ? decision.edit : undefined;
    const existing = existingOf(decided);
    // The server takes an existing individual or a class edit, never both.
    if (decision.kind === "class" && existing) return;
    // A decided one is decided again: checked first, so a refusal reopens nothing.
    const redeciding = !isAwaiting(decided);
    if (decision.kind !== "reject") {
      const blocked = redeciding
        ? isRelationship(decided) &&
          acceptBlocked({ ...decided, status: "pending" }, operations, edit)
        : acceptBlocked(decided, operations, edit);
      if (blocked) return;
    }
    let operation = decided;
    let current = operations;
    if (redeciding) {
      const reopened = await reopen(decided);
      if (!reopened) return;
      ({ operation, operations: current } = reopened);
    }
    const reviewMs = { [operation.id]: clock.spentOn(operation.id) };
    // A first decision moves on to the next awaiting one; a changed one stays to show it.
    const moveOn = (after: ProposedOperation[]) => {
      if (!redeciding) advance(operation.id, after);
    };
    if (decision.kind === "reject") {
      const rejected = await actions.rejectOperations([operation.id], decision.note, {
        reasonCode: decision.reasonCode,
        reviewMs,
        annotations: goldAnnotations(operation),
      });
      if (rejected) moveOn(current);
      return;
    }
    const outcome = await actions.accept([operation.id], {
      current,
      reviewMs,
      edits:
        decision.kind === "class"
          ? { [operation.id]: { class_ids: [decision.classId] } }
          : edit
            ? { [operation.id]: edit }
            : undefined,
      chosenAlternatives: existing ? { [operation.id]: existing } : undefined,
      annotations: goldAnnotations(
        operation,
        decision.kind === "class" ? decision.classId : undefined,
      ),
    });
    const after = appliedOutcome(operation, outcome);
    if (!after) return;
    if (decision.kind === "class") {
      setRecentClasses((recent) => rememberPick(recent, decision.classId));
    }
    moveOn(after);
  };

  // Keys: A correct, 1-3 a suggested class, X the reasons, J / K next and previous.
  const onKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onKey.current = (event) => {
    // While the add form is open, keys are its own; Escape closes it wherever focus went.
    if (adding) {
      if (event.key === "Escape" && !event.defaultPrevented) closeAdding();
      return;
    }
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    if (actions.forceRequest || ignoresKeys(event.target)) return;
    const key = event.key.toLowerCase();
    if (key === "j" || key === "k") {
      const next = step(shownOrder, selectedId, key === "j" ? 1 : -1);
      if (next) setSelectedId(next);
      event.preventDefault();
      return;
    }
    // Holding a key down decides once.
    if (event.repeat || !selected || !deciding || !isAwaiting(selected)) return;
    if (key === "a") {
      event.preventDefault();
      void decide(selected, { kind: "correct" });
    } else if (key === "x") {
      event.preventDefault();
      // A reason, or (in gold mode, before a note is written) the note it needs.
      const reason = reasonsRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)");
      (reason ?? document.getElementById("review-note"))?.focus();
    } else if (["1", "2", "3"].includes(key) && isElement(selected) && !existingOf(selected)) {
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
          <Button variant="primary" size="sm" onClick={onFinish} data-testid="review-finish">
            Finish review
          </Button>
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

      <ReviewPillsProvider value={pills}>
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
            groups={shownGroups}
            filter={filter}
            onFilter={setFilter}
            awaiting={awaitingCount}
            total={progress.total}
            rowOf={rowOf}
            selectedId={selectedId}
            link={link}
          />
          {selected ? (
            <ReviewInspector
              key={selected.id}
              operation={selected}
              operations={operations}
              names={names}
              schema={schema}
              endOf={endOf}
              endCandidates={endCandidates}
              taxonomyId={proposal.taxonomy_id}
              datasetId={proposal.dataset_id}
              nearChoice={nearChoiceOf(selected)}
              onNearChoice={(choice) =>
                setNearChoices((all) => ({ ...all, [selected.id]: choice }))
              }
              pickable={pickable}
              classesLoading={classesLoading}
              suggestions={suggestions}
              recentIds={recentClasses}
              onForgetClass={(classId) => setRecentClasses((recent) => forgetPick(recent, classId))}
              deciding={deciding}
              busy={actions.busy}
              reasonsRef={reasonsRef}
              onCorrect={() => void decide(selected, { kind: "correct" })}
              onPickClass={(classId) => void decide(selected, { kind: "class", classId })}
              onReject={(reasonCode, note) =>
                void decide(selected, { kind: "reject", reasonCode, note })
              }
              onAcceptEdited={(edit) => void decide(selected, { kind: "edit", edit })}
              onShowPassage={(quote) => showPassage(selected.id, quote)}
              gold={
                gold
                  ? {
                      goldTier: goldTierOf(gold, selected),
                      aliases: goldElementOf(gold, selected)?.aliases ?? [],
                      acceptableIds: classesByRef(
                        goldElementOf(gold, selected)?.acceptableClasses ?? [],
                        classes ?? [],
                      ).map((c) => c.id),
                      draft: draftOf(selected),
                      onDraft: (draft) =>
                        setGoldDrafts((all) => ({ ...all, [selected.id]: draft })),
                    }
                  : undefined
              }
            />
          ) : (
            <p className="review-pane review-pane--inspector review-muted">
              This proposal has no elements to review.
            </p>
          )}
        </div>
        {overlay.overlay}
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
