import { useEffect, useRef } from "react";
import type { ProposedOperation } from "@/api/services/proposals";
import { useToasts } from "@/components/ui/Toast";
import { isAwaiting } from "../proposalModel";
import {
  END_REJECTED_REASON,
  endRejectedNote,
  endsToDecide,
  isElement,
  isRelationship,
  seqList,
  step,
} from "./reviewModel";
import type { InspectorModel } from "./useInspectorModel";

/** Input types that take typed text: keys pressed in them are not page commands. */
const TEXT_INPUTS = new Set([
  "text",
  "search",
  "email",
  "url",
  "tel",
  "password",
  "number",
  "date",
  "datetime-local",
  "month",
  "time",
  "week",
]);

/**
 * Keys typed into a field, or pressed in a dialog, are not page commands. A
 * checkbox, radio, button or slider doesn't take letters, so J / K / A / X keep
 * working after a click on one.
 */
export function ignoresKeys(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const textInput =
    target instanceof HTMLInputElement && TEXT_INPUTS.has((target.type || "text").toLowerCase());
  return (
    target.isContentEditable ||
    textInput ||
    ["TEXTAREA", "SELECT"].includes(target.tagName) ||
    !!target.closest('[role="dialog"]')
  );
}

interface ReviewKeysOptions {
  /** The rows top to bottom, as the list shows them: J / K walk them. */
  order: string[];
  selectedId?: string;
  select: (operationId: string) => void;
  selected?: ProposedOperation;
  operations: ProposedOperation[];
  model: Pick<InspectorModel, "deciding" | "decide" | "suggestions" | "existingOf">;
  /** No keys while true (a confirmation open, the wide diff's own keys). */
  paused?: boolean;
  /** The reason step, as Not an element or Reject opens it. */
  onReasons: () => void;
  /** Whether A accepts this one as it stands; default: anything awaiting. */
  acceptsByKey?: (operation: ProposedOperation) => boolean;
}

/**
 * The review keys, on the window: J / K next and previous, A accept (correct),
 * X the reasons, 1-3 a suggested class for an element. On a relationship whose
 * end was rejected, X rejects it too and A says why it can't be accepted.
 * Holding a key down decides once.
 */
export function useReviewKeys(options: ReviewKeysOptions) {
  const { toast } = useToasts();
  const onKey = useRef<(event: KeyboardEvent) => void>(() => {});
  onKey.current = (event) => {
    const {
      order,
      selectedId,
      select,
      selected,
      operations,
      model,
      paused,
      onReasons,
      acceptsByKey,
    } = options;
    if (paused || event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    if (ignoresKeys(event.target)) return;
    const key = event.key.toLowerCase();
    if (key === "j" || key === "k") {
      const next = step(order, selectedId, key === "j" ? 1 : -1);
      if (next) select(next);
      event.preventDefault();
      return;
    }
    if (event.repeat || !selected || !model.deciding || !isAwaiting(selected)) return;
    const endRejected = isRelationship(selected) ? endsToDecide(selected, operations).rejected : [];
    if (key === "a" && endRejected.length > 0) {
      event.preventDefault();
      toast(
        "info",
        "This relationship can't be accepted",
        `${seqList(endRejected)} ${endRejected.length === 1 ? "was" : "were"} rejected: press X to reject it too, or give it another end.`,
      );
    } else if (key === "a") {
      if (acceptsByKey && !acceptsByKey(selected)) return;
      event.preventDefault();
      void model.decide(selected, { kind: "correct" });
    } else if (key === "x" && endRejected.length > 0) {
      event.preventDefault();
      void model.decide(selected, {
        kind: "reject",
        reasonCode: END_REJECTED_REASON,
        note: endRejectedNote(endRejected.map((e) => e.seq)),
      });
    } else if (key === "x") {
      event.preventDefault();
      onReasons();
    } else if (
      ["1", "2", "3"].includes(key) &&
      isElement(selected) &&
      !model.existingOf(selected)
    ) {
      const suggestion = model.suggestions[Number(key) - 1];
      if (!suggestion) return;
      event.preventDefault();
      void model.decide(selected, { kind: "class", classId: suggestion.id });
    }
  };
  useEffect(() => {
    const listener = (event: KeyboardEvent) => onKey.current(event);
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);
}
