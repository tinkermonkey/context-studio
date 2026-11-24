import { useMemo, useRef, useState } from "react";
import { SMALL_SET_LIMIT } from "@/api/config";
import { useTaxonomyClasses } from "@/api/hooks/ontology/useClasses";
import { useIndividuals, useIndividualsByIds } from "@/api/hooks/ontology/useIndividuals";
import type { ChangeProposal, ProposedOperation, RejectionReason } from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { takesDecisions } from "../decisionModel";
import { useHoverOverlay } from "../HoverOverlay";
import { isAwaiting } from "../proposalModel";
import {
  chosenAlternative,
  defaultNearMatchChoice,
  isNearMatch,
  sourcePassagesOf,
  type NearMatchChoice,
} from "../sourceModel";
import type { OperationContext } from "../useOperationContext";
import type { ApplyOutcome, ProposalActions } from "../useProposalActions";
import type { ReviewInspectorProps, ReviewNames } from "./ReviewInspector";
import type { OperationLink, ReviewPillsValue } from "./ReviewPills";
import type { EndCandidate, EndInfo } from "./ReviewRelationship";
import { useReviewSchema } from "./useReviewSchema";
import type { useReviewClock } from "./useReviewClock";
import {
  END_REJECTED_REASON,
  awaitingRelationshipsOf,
  endOperation,
  endRejectedNote,
  endsToDecide,
  forgetPick,
  isElement,
  isRelationship,
  relationshipsOf,
  rememberPick,
  shownClassId,
  shownFields,
  shownTitle,
  suggestedClasses,
  verdictLabel,
  verdictOf,
} from "./reviewModel";
import {
  EMPTY_DRAFT,
  annotationOf,
  classesByRef,
  goldCheckOf,
  goldElementOf,
  goldTierOf,
  type GoldDraft,
} from "./goldModel";

/** A decision on one operation, as the inspector and its keys make it. */
export type Decision =
  | { kind: "correct" }
  | { kind: "class"; classId: string }
  | { kind: "edit"; edit: Record<string, string> }
  | { kind: "reject"; reasonCode: RejectionReason; note: string };

export interface InspectorModelOptions {
  /** The page's proposal actions, so the inspector and the page share one busy state. */
  actions: ProposalActions;
  /** The page's names for what operations refer to. */
  context: OperationContext;
  /** The operation the inspector shows: its suggestions and end candidates are loaded. */
  selected: ProposedOperation | undefined;
  /** An operation's link: the pills and relationship cards select it with it. */
  link: (operationId: string) => OperationLink;
  /** Whether the inspector takes decisions; defaults to whether the proposal does. */
  deciding?: boolean;
  /** Review timing: each decision records the active time on its operation. */
  clock?: ReturnType<typeof useReviewClock>;
  /** After a first decision on `decidedId`: the page moves on (the Review page's next awaiting). */
  onDecided?: (decidedId: string, after: ProposedOperation[]) => void;
}

/**
 * What the review inspector needs for any operation of a proposal: classes and
 * the schema, names for pills, a relationship's ends and what they can change to,
 * gold mode, the classes picked recently, a near match's choice, and the decision
 * itself. The Review page and proposal detail share it, so both open the same
 * inspector with the same pills and hovers.
 */
export function useInspectorModel(
  proposal: ChangeProposal | undefined,
  {
    actions,
    context,
    selected,
    link,
    deciding: decidingOption,
    clock,
    onDecided,
  }: InspectorModelOptions,
) {
  const { toast } = useToasts();
  const taxonomyId = proposal?.taxonomy_id ?? "";
  const operations = useMemo(() => proposal?.operations ?? [], [proposal]);
  // The operations as they stand now, for a toast's action clicked after later renders.
  const operationsRef = useRef(operations);
  operationsRef.current = operations;
  const elements = useMemo(() => operations.filter(isElement), [operations]);
  const relationships = useMemo(() => operations.filter(isRelationship), [operations]);

  // Classes. Until they load, no class can be named, defined or picked (a failure falls back to ids).
  const { classes, isError: classesFailed } = useTaxonomyClasses(taxonomyId, !!taxonomyId);
  const classById = useMemo(() => new Map((classes ?? []).map((c) => [c.id, c])), [classes]);
  const pickable = useMemo(() => (classes ?? []).filter((c) => !c.derived), [classes]);
  const classesLoading = !classes && !classesFailed;

  // The schema: every relationship type, with the taxonomy's predicate catalog.
  const schema = useReviewSchema(taxonomyId);

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
    const endTitle = (value: unknown, operation: ProposedOperation) => {
      const create = endOperation(value, operations);
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
        quote: sourcePassagesOf(create).find((p) => p.quote)?.quote ?? undefined,
        relationships: relationshipsOf(create, operations).length,
      };
    }
    const found = endIndividuals?.items.find((i) => i.id === value);
    return {
      title: found?.title ?? (typeof value === "string" ? value : "?"),
      classId: found?.class_ids?.[0],
      status: found ? "in the workspace" : "not found",
    };
  };

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
  const rememberClass = (classId: string) =>
    setRecentClasses((recent) => rememberPick(recent, classId));
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
  const overlay = useHoverOverlay("#review-inspector", { lingerMs: 150, width: 320 });
  const pills: ReviewPillsValue = { schema, overlay, link };

  const deciding = decidingOption ?? (!!proposal && takesDecisions(proposal));

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

  /**
   * Reject the relationships still awaiting a decision that use a rejected element,
   * noting that an end was rejected (the counterpart of a reopen reopening them).
   */
  const rejectRelationshipsOf = async (element: ProposedOperation) => {
    const using = awaitingRelationshipsOf(element, operationsRef.current);
    if (using.length === 0) return;
    await actions.rejectOperations(
      using.map((o) => o.id),
      endRejectedNote([element.seq]),
      { reasonCode: END_REJECTED_REASON },
    );
  };

  /** After rejecting an element: offer to reject the awaiting relationships that use it. */
  const offerToRejectRelationships = (element: ProposedOperation, after: ProposedOperation[]) => {
    const using = awaitingRelationshipsOf(element, after);
    if (using.length === 0) return;
    const one = using.length === 1;
    toast(
      "info",
      `${using.length} relationship${one ? " uses" : "s use"} ${shownTitle(element)}: reject ${one ? "it" : "them"} too?`,
      `${using.map((o) => `#${o.seq}`).join(", ")} would be rejected as "an end was rejected".`,
      {
        action: {
          label: one ? "Reject it too" : "Reject them too",
          onAction: () => void rejectRelationshipsOf(element),
        },
        autoDismissMs: 15000,
      },
    );
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
    const reviewMs = clock ? { [operation.id]: clock.spentOn(operation.id) } : undefined;
    // A first decision moves on; a changed one stays to show it.
    const moveOn = (after: ProposedOperation[]) => {
      if (!redeciding) onDecided?.(operation.id, after);
    };
    if (decision.kind === "reject") {
      const rejected = await actions.rejectOperations([operation.id], decision.note, {
        reasonCode: decision.reasonCode,
        reviewMs,
        annotations: goldAnnotations(operation),
      });
      if (!rejected) return;
      if (isElement(operation)) offerToRejectRelationships(operation, current);
      moveOn(current);
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
    if (decision.kind === "class") rememberClass(decision.classId);
    moveOn(after);
  };

  /** The inspector's props for `operation`, but for what only the page knows. */
  const inspectorProps = (
    operation: ProposedOperation,
  ): Omit<ReviewInspectorProps, "onShowPassage" | "rejectPrompt"> => {
    const goldEntry = gold ? goldElementOf(gold, operation) : undefined;
    return {
      operation,
      operations,
      names,
      schema,
      endOf,
      endCandidates,
      taxonomyId,
      datasetId: proposal?.dataset_id,
      nearChoice: nearChoiceOf(operation),
      onNearChoice: (choice) => setNearChoices((all) => ({ ...all, [operation.id]: choice })),
      pickable,
      classesLoading,
      suggestions,
      recentIds: recentClasses,
      onForgetClass: (classId) => setRecentClasses((recent) => forgetPick(recent, classId)),
      deciding,
      busy: actions.busy,
      onCorrect: () => void decide(operation, { kind: "correct" }),
      onPickClass: (classId) => void decide(operation, { kind: "class", classId }),
      onReject: (reasonCode, note) => void decide(operation, { kind: "reject", reasonCode, note }),
      onAcceptEdited: (edit) => void decide(operation, { kind: "edit", edit }),
      onRejectRelationships: () => void rejectRelationshipsOf(operation),
      gold: gold
        ? {
            goldTier: goldTierOf(gold, operation),
            aliases: goldEntry?.aliases ?? [],
            acceptableIds: classesByRef(goldEntry?.acceptableClasses ?? [], classes ?? []).map(
              (c) => c.id,
            ),
            draft: draftOf(operation),
            onDraft: (draft) => setGoldDrafts((all) => ({ ...all, [operation.id]: draft })),
          }
        : undefined,
    };
  };

  return {
    classById,
    pickable,
    classesLoading,
    schema,
    names,
    endOf,
    gold,
    recentClasses,
    rememberClass,
    suggestions,
    existingOf,
    deciding,
    decide,
    pills,
    overlay,
    inspectorProps,
  };
}

export type InspectorModel = ReturnType<typeof useInspectorModel>;
