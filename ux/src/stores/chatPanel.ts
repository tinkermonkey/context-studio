import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { EntityKind } from "@/lib/entityPaths";

/** An entity the user asked about ("Ask about this"), tied to the page it was asked on. */
export interface AskAboutContext {
  kind: EntityKind;
  id: string;
  title: string;
  pathname: string;
}

interface ChatPanelState {
  /** Whether the docked chat column is open (persisted). */
  open: boolean;
  /** Entity the user asked about from an entity page; overrides the route-derived context. */
  askAbout: AskAboutContext | null;
  /** Context key whose "Viewing: X" chip the user removed. */
  dismissedContextKey: string | null;
  /** Bumped to ask the panel to start a new conversation. */
  newChatRequest: number;
  /** Bumped to ask the panel to focus its composer. */
  focusRequest: number;
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
  askAboutEntity: (context: AskAboutContext) => void;
  dismissContext: (key: string) => void;
  requestNewChat: () => void;
}

export const useChatPanelStore = create<ChatPanelState>()(
  persist(
    (set) => ({
      open: false,
      askAbout: null,
      dismissedContextKey: null,
      newChatRequest: 0,
      focusRequest: 0,
      openPanel: () => set((s) => ({ open: true, focusRequest: s.focusRequest + 1 })),
      closePanel: () => set({ open: false }),
      togglePanel: () =>
        set((s) => ({ open: !s.open, focusRequest: s.open ? s.focusRequest : s.focusRequest + 1 })),
      askAboutEntity: (askAbout) =>
        set((s) => ({
          open: true,
          askAbout,
          dismissedContextKey: null,
          focusRequest: s.focusRequest + 1,
        })),
      dismissContext: (key) => set({ dismissedContextKey: key }),
      requestNewChat: () =>
        set((s) => ({
          open: true,
          newChatRequest: s.newChatRequest + 1,
          focusRequest: s.focusRequest + 1,
        })),
    }),
    {
      name: "chat-panel",
      partialize: (state) => ({ open: state.open }),
    },
  ),
);
