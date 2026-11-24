/**
 * Which left pane of the review page is folded to a rail (#1665): the source,
 * the list, or neither. One rail at a time; the choice is remembered per
 * viewer in local storage, and a storage that fails (a private window,
 * blocked site data) just forgets it.
 */
import { useCallback, useState } from "react";

export type PaneFold = "source" | "list" | undefined;

export const PANE_FOLD_KEY = "context-studio.review.folded";

export function readPaneFold(): PaneFold {
  try {
    const value = window.localStorage.getItem(PANE_FOLD_KEY);
    return value === "source" || value === "list" ? value : undefined;
  } catch {
    return undefined;
  }
}

function writePaneFold(fold: PaneFold) {
  try {
    if (fold) window.localStorage.setItem(PANE_FOLD_KEY, fold);
    else window.localStorage.removeItem(PANE_FOLD_KEY);
  } catch {
    // Remembering is a convenience: without storage the fold lasts for this page only.
  }
}

/** The fold, remembered: setting a pane folds it (unfolding the other); undefined unfolds. */
export function usePaneFold() {
  const [fold, setFoldState] = useState<PaneFold>(readPaneFold);
  const setFold = useCallback((next: PaneFold) => {
    setFoldState(next);
    writePaneFold(next);
  }, []);
  return { fold, setFold };
}
