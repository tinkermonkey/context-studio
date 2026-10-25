import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { QUERY_KEYS } from "@/api/config";
import { chatService, type PageContext } from "@/api/services/chat";
import {
  addEntities,
  addPageContext,
  applyStreamEvent,
  displayMessagesFromStored,
  knownEntitiesFromStored,
  type DisplayMessage,
  type KnownEntities,
} from "@/components/chat/chatModel";

/** The configured chat model and whether a provider can serve it. */
export function useChatStatus() {
  return useQuery({
    queryKey: QUERY_KEYS.chatStatus,
    queryFn: () => chatService.getStatus(),
    staleTime: 30_000,
  });
}

export interface ChatSession {
  conversationId: string | null;
  messages: DisplayMessage[];
  /** Entity ids answers may link to (tool results and page contexts). */
  known: KnownEntities;
  loading: boolean;
  streaming: boolean;
  /** Failure loading the conversation (send failures show on their message). */
  loadError: string | null;
  send: (text: string, pageContext: PageContext | null) => Promise<void>;
  newChat: () => void;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}

/**
 * The panel's conversation: resumes the latest one on mount, streams each
 * message's turn, and starts a new conversation on request. A conversation is
 * created on the first message, so "New chat" never leaves empty ones behind.
 */
export function useChatSession(): ChatSession {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [known, setKnown] = useState<KnownEntities>(() => new Map());
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [latest] = await chatService.listConversations(1);
        if (latest && !cancelled) {
          const detail = await chatService.getConversation(latest.id);
          if (cancelled) return;
          setConversationId(detail.id);
          setMessages(displayMessagesFromStored(detail.messages));
          setKnown(knownEntitiesFromStored(detail.messages));
        }
      } catch (error) {
        if (!cancelled) setLoadError(errorMessage(error));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, []);

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    setConversationId(null);
    setMessages([]);
    setKnown(new Map());
    setLoadError(null);
    setStreaming(false);
  }, []);

  const send = useCallback(
    async (text: string, pageContext: PageContext | null) => {
      const now = new Date().toISOString();
      const assistantId = `pending-${Date.now()}`;
      setMessages((prev) => [
        ...prev,
        {
          id: `user-${Date.now()}`,
          role: "user",
          blocks: [{ type: "text", text }],
          createdAt: now,
        },
        { id: assistantId, role: "assistant", blocks: [], createdAt: now },
      ]);
      if (pageContext) {
        setKnown((prev) => {
          const next = new Map(prev);
          addPageContext(next, pageContext);
          return next;
        });
      }
      const updateAssistant = (update: (m: DisplayMessage) => DisplayMessage) =>
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? update(m) : m)));

      setStreaming(true);
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        let id = conversationId;
        if (!id) {
          id = (await chatService.createConversation()).id;
          setConversationId(id);
        }
        const stream = chatService.streamMessage(
          id,
          { text, page_context: pageContext },
          controller.signal,
        );
        for await (const event of stream) {
          if (event.type === "tool_end") {
            setKnown((prev) => {
              const next = new Map(prev);
              addEntities(next, event.entities);
              return next;
            });
          }
          updateAssistant((m) => applyStreamEvent(m, event));
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          updateAssistant((m) => ({ ...m, error: errorMessage(error) }));
        }
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
          setStreaming(false);
        }
      }
    },
    [conversationId],
  );

  return { conversationId, messages, known, loading, streaming, loadError, send, newChat };
}
