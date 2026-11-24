import { useLayoutEffect, useRef, useState } from "react";

/** Space left under the panes at the bottom of the window. */
const PANES_BOTTOM_GAP = 24;
/** The panes never get shorter than this, however little of the window is left. */
const PANES_MIN_HEIGHT = 480;

/**
 * The height that makes the panes fill the window below where they start,
 * worked out when the page lays out and whenever the window resizes.
 */
export function usePanesHeight(ready: boolean) {
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
