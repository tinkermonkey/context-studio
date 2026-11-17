import { useCallback, useEffect, useRef } from "react";
import { activeMsAt, recordActivity, startClock, type ActiveClock } from "./reviewTiming";

/** Pointer and key events that show the reviewer is at the page. */
const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel"] as const;

/**
 * Two active-time clocks for a review: one for the page, and one for the
 * selected element, restarted whenever another element is selected. Kept in
 * refs: activity never re-renders the page.
 */
export function useReviewClock() {
  const page = useRef<ActiveClock>(startClock(Date.now()));
  const element = useRef<{ id: string; clock: ActiveClock } | null>(null);

  useEffect(() => {
    const onActivity = () => {
      const now = Date.now();
      page.current = recordActivity(page.current, now);
      if (element.current) {
        element.current = { ...element.current, clock: recordActivity(element.current.clock, now) };
      }
    };
    for (const name of ACTIVITY_EVENTS)
      window.addEventListener(name, onActivity, { passive: true });
    return () => {
      for (const name of ACTIVITY_EVENTS) window.removeEventListener(name, onActivity);
    };
  }, []);

  /** Start timing an element, unless it is the one being timed. */
  const startElement = useCallback((id: string | undefined) => {
    if (!id) {
      element.current = null;
    } else if (element.current?.id !== id) {
      element.current = { id, clock: startClock(Date.now()) };
    }
  }, []);

  /** Active milliseconds on this element since it was selected; 0 when it isn't timed. */
  const spentOn = useCallback(
    (id: string) =>
      element.current?.id === id ? activeMsAt(element.current.clock, Date.now()) : 0,
    [],
  );

  /** Active milliseconds on the page. */
  const pageMs = useCallback(() => activeMsAt(page.current, Date.now()), []);

  return { startElement, spentOn, pageMs };
}
