import { useMemo, useRef, useState } from "react";
import type { PaneRailMark } from "@tinkermonkey/heimdall-ui";
import { useAddProposalIndividual } from "@/api/hooks/proposals";
import { useSource, useSourceText } from "@/api/hooks/sources/useSource";
import type { ChangeProposal, ProposedOperation } from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { AddElementPopover } from "./AddElementPopover";
import {
  addErrorMessage,
  addedOperation,
  additionsBlocked,
  proposalSourceId,
  toSourcePassage,
  type SelectedPassage,
} from "./addFromText";
import type { Tier } from "./goldModel";
import { ReviewSourcePane, type PopoverAnchor } from "./ReviewSourcePane";
import {
  VERDICT_CHIP,
  VERDICT_LEGEND,
  extractedFromSource,
  isElement,
  isRelationship,
  reviewSourceId,
  reviewSpans,
  verdictOf,
} from "./reviewModel";
import type { InspectorModel } from "./useInspectorModel";

/** An extraction of individuals: client_metadata.pipeline, or its origin's pipeline_type. */
const INDIVIDUAL_EXTRACTION = "individual_extraction";
import type { useReviewClock } from "./useReviewClock";

interface SourcePaneOptions {
  proposal: ChangeProposal | undefined;
  operations: ProposedOperation[];
  selected: ProposedOperation | undefined;
  selectedId: string | undefined;
  select: (operationId: string) => void;
  model: Pick<
    InspectorModel,
    "names" | "pickable" | "classesLoading" | "recentClasses" | "rememberClass" | "gold"
  >;
  clock: ReturnType<typeof useReviewClock>;
  /** Fold the pane to a rail; without it the pane doesn't fold. */
  onFold?: () => void;
}

/**
 * The source pane of a proposal whose elements came from a source (#1664): the
 * text with every element's passages highlighted by verdict (and the open
 * relationship's), a passage shown from the inspector, and adding an element
 * the extraction missed by selecting its text. `shown` is false for a proposal
 * with no source: the page has no source pane then.
 */
export function useSourcePane({
  proposal,
  operations,
  selected,
  selectedId,
  select,
  model,
  clock,
  onFold,
}: SourcePaneOptions) {
  const { toast } = useToasts();
  const elements = useMemo(() => operations.filter(isElement), [operations]);
  // The source the proposal records it was extracted from, else the one its passages cite.
  const recordedSourceId = proposalSourceId(proposal);
  // The source the elements' and relationships' passages cite most.
  const citedSourceId = useMemo(
    () => reviewSourceId(operations.filter((o) => isElement(o) || isRelationship(o))),
    [operations],
  );
  // A pane only where there is something to review against the text: elements or
  // relationships that cite it, or an extraction of individuals from it (whose add
  // form works even before anything is found). A schema extraction, which records
  // its source too, gets none.
  const individualExtraction =
    proposal?.client_metadata?.pipeline === INDIVIDUAL_EXTRACTION ||
    proposal?.origin?.pipeline_type === INDIVIDUAL_EXTRACTION;
  const shown = extractedFromSource(proposal) || (!!recordedSourceId && individualExtraction);
  const sourceId = shown ? (recordedSourceId ?? citedSourceId) : undefined;
  const { data: source, isError: sourceFailed } = useSource(sourceId);
  const readable = !!source && source.status === "ready" && !source.removed_at;
  const { data: sourceText, isError: textFailed } = useSourceText(sourceId, null, {
    enabled: readable,
  });
  // The highlighted passages: every element's, and the open relationship's.
  const elementSpans = useMemo(
    () =>
      sourceId && sourceText
        ? reviewSpans(elements, sourceId, sourceText.text, sourceText.start)
        : [],
    [elements, sourceId, sourceText],
  );
  const spans = useMemo(
    () =>
      selected && isRelationship(selected) && sourceId && sourceText
        ? [...elementSpans, ...reviewSpans([selected], sourceId, sourceText.text, sourceText.start)]
        : elementSpans,
    [elementSpans, selected, sourceId, sourceText],
  );

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
  const textRef = useRef<HTMLDivElement>(null);
  /** Close the add form; focus goes back to the source text unless the reviewer clicked away. */
  const closeAdding = ({ refocus = true } = {}) => {
    setAdding(undefined);
    setAddError(undefined);
    if (refocus) textRef.current?.focus({ preventScroll: true });
  };
  const addElement = async (title: string, classId: string, tier?: Tier) => {
    if (!proposal || !adding || !recordedSourceId || !sourceText || addIndividual.isPending) return;
    // The server counts offsets in code points, the browser in UTF-16 units.
    const passage = toSourcePassage(adding.passage, sourceText.text, sourceText.start);
    const before = new Set(operations.map((o) => o.id));
    try {
      const after = await addIndividual.mutateAsync({
        id: proposal.id,
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
      model.rememberClass(classId);
      const added = addedOperation(before, after);
      if (added) select(added.id);
      if (added?.status === "failed") {
        toast("error", `Added ${title}, but it didn't apply`, added.reason ?? undefined);
      } else {
        toast("success", `Added ${title}`, `As ${model.names.classLabel(classId)}`);
      }
    } catch (error) {
      setAddError(addErrorMessage(error, { title, classLabel: model.names.classLabel(classId) }));
    }
  };

  // The rail's map while the pane is folded: each highlight at its place in the text,
  // in its verdict's tone (named in its label too, for forced colours).
  const textLength = sourceText?.text.length ?? 0;
  const railMarks = useMemo((): PaneRailMark[] => {
    if (!textLength) return [];
    return spans.flatMap((span) => {
      if (span.start == null) return [];
      const operation = operations.find((o) => o.id === span.key);
      const verdict = operation ? verdictOf(operation) : "awaiting";
      return [
        {
          id: span.key,
          position: span.start / textLength,
          tone: VERDICT_CHIP[verdict] as PaneRailMark["tone"],
          label: `${VERDICT_LEGEND[verdict]}: ${span.quote}`,
        },
      ];
    });
  }, [spans, operations, textLength]);
  const selectedSpan = spans.find((s) => s.key === selectedId);
  /** Show a highlight of `operationId` (the first, or the one at `start`) in the text. */
  const showSpan = (operationId: string, start?: number) => {
    const span =
      spans.find((s) => s.key === operationId && (start === undefined || s.start === start)) ??
      spans.find((s) => s.key === operationId);
    if (span?.start != null) setFocus({ start: span.start, nonce: Date.now() });
  };

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

  const pane = (
    <ReviewSourcePane
      title={source?.title}
      text={sourceText?.text}
      unavailable={unavailable}
      spans={spans}
      verdictOf={(opId) => {
        const operation = operations.find((o) => o.id === opId);
        return operation ? verdictOf(operation) : "awaiting";
      }}
      titleOf={(opId) => {
        const operation = operations.find((o) => o.id === opId);
        return operation ? model.names.titleOf(operation) : opId;
      }}
      selectedId={selectedId}
      onSelect={select}
      focus={focus}
      textRef={textRef}
      onDismissPopover={() => closeAdding({ refocus: false })}
      onFold={onFold}
      onSelectText={canAdd ? openAdding : undefined}
      addBlocked={addBlocked}
      popoverAnchor={adding?.anchor}
      popover={
        adding && (
          <AddElementPopover
            key={`${adding.passage.start}-${adding.passage.end}`}
            passage={adding.passage}
            pickable={model.pickable}
            classesLoading={model.classesLoading}
            initialClassId={model.recentClasses[0]}
            classLabel={model.names.classLabel}
            classOf={model.names.classOf}
            busy={addIndividual.isPending}
            error={addError}
            onEdit={() => setAddError(undefined)}
            askTier={!!model.gold}
            onAdd={(title, classId, tier) => void addElement(title, classId, tier)}
            onCancel={() => closeAdding()}
          />
        )
      }
    />
  );

  return {
    /** A source pane only for a proposal extracted from a source, or whose elements cite one. */
    shown,
    source,
    pane,
    adding: !!adding,
    closeAdding,
    showPassage,
    showSpan,
    /** The folded pane's map: its highlights, and where the selection is in the text. */
    rail: {
      marks: railMarks,
      selectedPosition:
        selectedSpan?.start != null && textLength ? selectedSpan.start / textLength : undefined,
    },
  };
}
