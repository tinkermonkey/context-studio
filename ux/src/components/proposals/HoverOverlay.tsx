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
function overlayStyle(anchor: Element, container: string, width = OVERLAY_WIDTH): CSSProperties {
  const item = anchor.getBoundingClientRect();
  const panel = (anchor.closest(container) ?? anchor).getBoundingClientRect();
  if (panel.left >= width + OVERLAY_GAP * 2) {
    return { top: item.top, left: panel.left - width - OVERLAY_GAP, width };
  }
  const left = Math.min(item.left, window.innerWidth - width - OVERLAY_GAP);
  return { top: item.bottom + 4, left: Math.max(OVERLAY_GAP, left), width };
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
function OverlayCard({
  open,
  interactive,
  onEnter,
  onLeave,
}: {
  open: OpenOverlay;
  /** The pointer can reach the card and follow its links (it lingers). */
  interactive: boolean;
  /** The pointer reached the card: keep it open. */
  onEnter: () => void;
  onLeave: () => void;
}) {
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
      className={
        interactive ? "definition-overlay definition-overlay--interactive" : "definition-overlay"
      }
      style={{ ...open.style, top }}
      data-testid={open.testId}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
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
 * @param lingerMs How long the overlay stays after its item is left, so the
 *     pointer can move into it and follow a link there (0: it closes at once,
 *     and the pointer passes through it).
 * @param width The overlay's width in px.
 */
export function useHoverOverlay(
  container: string,
  { lingerMs = 0, width = OVERLAY_WIDTH }: { lingerMs?: number; width?: number } = {},
) {
  const [open, setOpen] = useState<OpenOverlay>();
  const timer = useRef<number | undefined>(undefined);
  const cancelHide = useCallback(() => window.clearTimeout(timer.current), []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const anchor = open?.anchor;
  useEffect(() => {
    if (!anchor) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(undefined);
    const onScroll = () =>
      setOpen((current) =>
        current && inView(current.anchor, container)
          ? { ...current, style: overlayStyle(current.anchor, container, width) }
          : undefined,
      );
    document.addEventListener("keydown", onKey);
    document.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, [anchor, container, width]);
  const show = useCallback(
    (id: string, content: ReactNode, target: Element, testId?: string) => {
      window.clearTimeout(timer.current);
      setOpen({
        id,
        content,
        anchor: target,
        style: overlayStyle(target, container, width),
        testId,
      });
    },
    [container, width],
  );
  const hide = useCallback(
    (id: string) => {
      const close = () => setOpen((current) => (current?.id === id ? undefined : current));
      window.clearTimeout(timer.current);
      if (lingerMs > 0) timer.current = window.setTimeout(close, lingerMs);
      else close();
    },
    [lingerMs],
  );
  return {
    show,
    hide,
    /** The id of the overlay shown, if any (for the item's aria-describedby). */
    openId: open?.id,
    overlay: open ? (
      <OverlayCard
        open={open}
        interactive={lingerMs > 0}
        onEnter={cancelHide}
        onLeave={() => hide(open.id)}
      />
    ) : null,
  };
}

export type HoverOverlay = ReturnType<typeof useHoverOverlay>;
