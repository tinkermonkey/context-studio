import { Fragment, useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Button,
  ChatComposer,
  ChatContainer,
  ChatDivider,
  ChatMessage,
  ChatSuggestions,
  Chip,
  Icon,
  ToolBlock,
  type ContextItem,
} from "@tinkermonkey/heimdall-ui";
import { useChatSession, useChatStatus } from "@/api/hooks/chat";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { useChatPanelStore } from "@/stores/chatPanel";
import { ChatAnswer } from "./ChatAnswer";
import type { DisplayMessage, KnownEntities } from "./chatModel";
import { useChatPageContext } from "./useChatPageContext";

const BASE_SUGGESTIONS = [
  "What's in this workspace?",
  "Which classes have the most individuals?",
  "What relationship types connect the layers?",
];

function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDay(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
}

function toolOutput(input: Record<string, unknown>, summary: string) {
  const rows: Array<{ key?: string; value: string }> = [];
  if (summary) rows.push({ key: "result", value: summary });
  const args = Object.entries(input)
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(" ");
  if (args) rows.push({ key: "input", value: args });
  return rows;
}

interface AssistantBodyProps {
  message: DisplayMessage;
  known: KnownEntities;
  pending: boolean;
}

/** An assistant turn: its tool calls as a stack of ToolBlocks, then the answer. */
function AssistantBody({ message, known, pending }: AssistantBodyProps) {
  return (
    <div className="chat-turn">
      {message.blocks.map((block, index) =>
        block.type === "tool" ? (
          <ToolBlock
            key={block.toolUseId}
            name={block.name}
            status={block.status}
            output={toolOutput(block.input, block.summary)}
            defaultCollapsed
            data-testid="chat-tool-block"
            data-status={block.status}
          />
        ) : (
          <ChatAnswer key={`text-${index}`} text={block.text} known={known} />
        ),
      )}
      {pending && message.blocks.length === 0 && (
        <span className="chat-turn__pending" data-testid="chat-pending">
          Thinking…
        </span>
      )}
      {message.error && (
        <div className="chat-turn__error" role="alert" data-testid="chat-turn-error">
          {message.error}
        </div>
      )}
    </div>
  );
}

/**
 * The docked chat column: the assistant's conversation about the workspace.
 * Resumes the latest conversation, sends the viewed page as context, and turns
 * entity links in answers into navigation that keeps the panel open.
 */
export function ChatPanel() {
  const navigate = useNavigate();
  const open = useChatPanelStore((s) => s.open);
  const closePanel = useChatPanelStore((s) => s.closePanel);
  const dismissContext = useChatPanelStore((s) => s.dismissContext);
  const newChatRequest = useChatPanelStore((s) => s.newChatRequest);
  const focusRequest = useChatPanelStore((s) => s.focusRequest);
  const status = useChatStatus();
  const session = useChatSession();
  const page = useChatPageContext();
  const [draft, setDraft] = useState("");
  const panelRef = useRef<HTMLElement>(null);

  const { newChat } = session;
  const handledNewChat = useRef(newChatRequest);
  useEffect(() => {
    if (newChatRequest !== handledNewChat.current) {
      handledNewChat.current = newChatRequest;
      newChat();
    }
  }, [newChatRequest, newChat]);

  // Focus the composer when the panel opens or is asked to; the composer is
  // disabled until the status loads, so retry once it's ready.
  const composerReady = Boolean(status.data?.available);
  useEffect(() => {
    if (open && composerReady) panelRef.current?.querySelector("textarea")?.focus();
  }, [focusRequest, open, composerReady]);

  const send = (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || session.streaming) return;
    setDraft("");
    void session.send(trimmed, page.pageContext);
  };

  const contextItems: ContextItem[] = page.dismissed
    ? []
    : [{ id: page.key, label: `Viewing: ${page.label}` }];
  const suggestions = page.pageContext?.entity_id
    ? [`Tell me about ${page.label}`, ...BASE_SUGGESTIONS]
    : BASE_SUGGESTIONS;
  const available = status.data?.available ?? false;

  let thread;
  if (session.loading) {
    thread = (
      <div className="chat-panel__state" data-testid="chat-loading">
        Loading conversation…
      </div>
    );
  } else if (session.messages.length === 0) {
    thread = (
      <div className="chat-panel__state" data-testid="chat-empty-thread">
        <p className="chat-panel__intro">
          Ask about the schema or the data. Answers link to the entities they mention.
        </p>
        <ChatSuggestions suggestions={suggestions} onSelect={send} data-testid="chat-suggestions" />
      </div>
    );
  } else {
    let lastDay = "";
    thread = session.messages.map((message, index) => {
      const day = formatDay(message.createdAt);
      const divider = day && day !== lastDay ? <ChatDivider label={day} /> : null;
      lastDay = day || lastDay;
      const pending = session.streaming && index === session.messages.length - 1;
      return (
        <Fragment key={message.id}>
          {divider}
          {message.role === "user" ? (
            <ChatMessage
              role="user"
              senderName="You"
              timestamp={formatTime(message.createdAt)}
              body={message.blocks.map((b) => (b.type === "text" ? b.text : "")).join("")}
              data-testid="chat-message-user"
            />
          ) : (
            <ChatMessage
              role="bot"
              senderName="Assistant"
              avatar="AI"
              timestamp={formatTime(message.createdAt)}
              body={<AssistantBody message={message} known={session.known} pending={pending} />}
              data-testid="chat-message-assistant"
            />
          )}
        </Fragment>
      );
    });
  }

  return (
    <aside
      ref={panelRef}
      id="chat-panel"
      className="chat-panel"
      data-testid="chat-panel"
      aria-label="Chat assistant"
      hidden={!open}
    >
      <header className="chat-panel__header">
        <span className="chat-panel__title">
          <Icon name="bot" size={14} /> Assistant
        </span>
        {status.data && (
          <span data-testid="chat-model-chip">
            <Chip variant={available ? "neutral" : "rose"}>{status.data.model}</Chip>
          </span>
        )}
        <span className="chat-panel__spacer" />
        <Button
          size="sm"
          variant="ghost"
          onClick={session.newChat}
          disabled={session.messages.length === 0 && !session.conversationId}
          data-testid="chat-new-button"
        >
          <Icon name="plus" size={12} /> New chat
        </Button>
        <button
          type="button"
          className="chat-panel__close"
          onClick={closePanel}
          aria-label="Close chat"
          data-testid="chat-close-button"
        >
          <Icon name="x" size={14} />
        </button>
      </header>

      {status.isError ? (
        <ErrorBanner
          error={status.error}
          onRetry={() => status.refetch()}
          compact
          message="Chat is unavailable"
        />
      ) : status.data && !available ? (
        <div className="chat-panel__setup" data-testid="chat-setup-required">
          <EmptyState
            icon={<Icon name="bot" size={22} />}
            title="Set up a chat model"
            description={`No configured provider serves “${status.data.model}”. Add an Anthropic or OpenRouter API key to config.json, or choose another chat model in Settings.`}
            action={{ label: "Open Settings", onClick: () => navigate({ to: "/app/settings" }) }}
            variant="compact"
          />
        </div>
      ) : (
        <ChatContainer
          className="chat-panel__container"
          data-testid="chat-thread"
          composer={
            <ChatComposer
              value={draft}
              onChange={setDraft}
              onSubmit={(value) => send(value)}
              placeholder="Ask about the schema or data…"
              label="Message the assistant"
              contextItems={contextItems}
              onContextChange={(items) => {
                if (items.length === 0) dismissContext(page.key);
              }}
              loading={session.streaming}
              disabled={!status.data}
              data-testid="chat-composer"
            />
          }
        >
          {session.loadError && (
            <ErrorBanner
              error={new Error(session.loadError)}
              message="Couldn't load the conversation"
              compact
            />
          )}
          {thread}
        </ChatContainer>
      )}
    </aside>
  );
}
