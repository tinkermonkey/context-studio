import { useEffect } from "react";
import { useRouterState } from "@tanstack/react-router";
import { ASK_ABOUT_EVENT, type AskAboutDetail } from "@/components/entity/EntityPageParts";
import { useKeyboardShortcut } from "@/hooks/useKeyboardShortcut";
import { useChatPanelStore } from "@/stores/chatPanel";
import { useCommandPaletteStore, type PaletteAction } from "@/stores/commandPalette";

const META: Array<"meta"> = ["meta"];

/**
 * Wire the chat panel's app-wide entry points: ⌘J, the "Ask about this page"
 * and "New chat" palette actions, and entity pages' "Ask about this" event
 * (opens the panel with that entity as the page context).
 */
export function useChatEntryPoints() {
  const pathname = useRouterState().location.pathname;
  const togglePanel = useChatPanelStore((s) => s.togglePanel);
  const openPanel = useChatPanelStore((s) => s.openPanel);
  const requestNewChat = useChatPanelStore((s) => s.requestNewChat);
  const askAboutEntity = useChatPanelStore((s) => s.askAboutEntity);
  const { registerActions, unregisterActions } = useCommandPaletteStore();

  useKeyboardShortcut({ key: "j", modifiers: META, onKeydown: togglePanel });

  useEffect(() => {
    const onAskAbout = (event: Event) => {
      const detail = (event as CustomEvent<AskAboutDetail>).detail;
      if (detail?.id) askAboutEntity({ ...detail, pathname });
    };
    window.addEventListener(ASK_ABOUT_EVENT, onAskAbout);
    return () => window.removeEventListener(ASK_ABOUT_EVENT, onAskAbout);
  }, [askAboutEntity, pathname]);

  useEffect(() => {
    const actions: PaletteAction[] = [
      {
        id: "chat-ask-about-page",
        label: "Ask about this page",
        description: "Open the assistant with this page as context",
        icon: "bot",
        shortcut: "⌘J",
        onSelect: openPanel,
      },
      {
        id: "chat-new",
        label: "New chat",
        description: "Start a new conversation with the assistant",
        icon: "bot",
        onSelect: requestNewChat,
      },
    ];
    registerActions(actions);
    return () => unregisterActions(actions.map((a) => a.id));
  }, [registerActions, unregisterActions, openPanel, requestNewChat]);
}
