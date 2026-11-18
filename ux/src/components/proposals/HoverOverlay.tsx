import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import "./proposals.css";

/** The overlay's width and its gap from the container's edge, in px. */
const OVERLAY_WIDTH = 360;
const OVERLAY_GAP = 12;

interface OpenOverlay {
  id: string;
  content: ReactNode;
  /** What it describes: a scroll moves the overlay along with it. */
  anchor: Element;
  style: CSSProperties;
  testId?: string;
}

/**
 * Where the overlay goes: level with its anchor, just left of the container
 * the anchor is in (an inspector), or under the anchor when there is no room
 * beside it.
 */
function overlayStyle(anchor: Element, container: string): CSSProperties {
  const item = anchor.getBoundingClientRect();
  const panel = (anchor.closest(container) ?? anchor).getBoundingClientRect();
  if (panel.left >= OVERLAY_WIDTH + OVERLAY_GAP * 2) {
    return { top: item.top, left: panel.left - OVERLAY_WIDTH - OVERLAY_GAP, width: OVERLAY_WIDTH };
  }
  const left = Math.min(item.left, window.innerWidth - OVERLAY_WIDTH - OVERLAY_GAP);
  return { top: item.bottom + 4, left: Math.max(OVERLAY_GAP, left), width: OVERLAY_WIDTH };
}

/** True while the anchor is in view: inside the window and its container's visible box. */
function inView(anchor: Element, container: string): boolean {
  const item = anchor.getBoundingClientRect();
  const panel = (anchor.closest(container) ?? anchor).getBoundingClientRect();
  return (
    item.bottom > Math.max(0, panel.top) && item.top < Math.min(window.innerHeight, panel.bottom)
  );
}

/** The overlay card, in a portal so the container's scroll can't clip it. */
function OverlayCard({ open }: { open: OpenOverlay }) {
  const ref = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(open.style.top as number);
  // A long overlay moves up so all of it stays in the window.
  useLayoutEffect(() => {
    const height = ref.current?.offsetHeight ?? 0;
    const wanted = open.style.top as number;
    setTop(Math.max(OVERLAY_GAP, Math.min(wanted, window.innerHeight - height - OVERLAY_GAP)));
  }, [open]);
  return createPortal(
    <div
      ref={ref}
      id={open.id}
      role="tooltip"
      className="definition-overlay"
      style={{ ...open.style, top }}
      data-testid={open.testId}
    >
      {open.content}
    </div>,
    document.body,
  );
}

/**
 * The app's hover overlay: what an item means, shown beside its container (an
 * inspector) while the item is hovered or focused. Escape dismisses it; a
 * scroll moves it along with its item and closes it once the item is out of
 * view. Render `overlay` once; call `show` from the item's mouse enter and
 * focus, `hide` from its mouse leave and blur.
 *
 * @param container A selector for the element the overlay sits beside.
 */
export function useHoverOverlay(container: string) {
  const [open, setOpen] = useState<OpenOverlay>();
  const anchor = open?.anchor;
  useEffect(() => {
    if (!anchor) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(undefined);
    const onScroll = () =>
      setOpen((current) =>
        current && inView(current.anchor, container)
          ? { ...current, style: overlayStyle(current.anchor, container) }
          : undefined,
      );
    document.addEventListener("keydown", onKey);
    document.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, [anchor, container]);
  const show = useCallback(
    (id: string, content: ReactNode, target: Element, testId?: string) =>
      setOpen({ id, content, anchor: target, style: overlayStyle(target, container), testId }),
    [container],
  );
  const hide = useCallback(
    (id: string) => setOpen((current) => (current?.id === id ? undefined : current)),
    [],
  );
  return {
    show,
    hide,
    /** The id of the overlay shown, if any (for the item's aria-describedby). */
    openId: open?.id,
    overlay: open ? <OverlayCard open={open} /> : null,
  };
}

export type HoverOverlay = ReturnType<typeof useHoverOverlay>;
