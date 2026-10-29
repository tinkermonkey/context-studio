import type { LinkKind } from "@/lib/entityPaths";
import type {
  ChatStreamEvent,
  EntityRef,
  PageContext,
  StoredChatMessage,
} from "@/api/services/chat";

/** One piece of an assistant turn as the panel shows it. */
export type DisplayBlock =
  | { type: "text"; text: string }
  | {
      type: "tool";
      toolUseId: string;
      name: string;
      input: Record<string, unknown>;
      status: "running" | "success" | "error";
      summary: string;
    };

/** A user question, or the assistant's whole turn (tool calls and answer text). */
export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  blocks: DisplayBlock[];
  createdAt: string;
  error?: string;
}

/** Entity ids the assistant may link to, mapped to their kind. */
export type KnownEntities = Map<string, string>;

const PAGE_KINDS: readonly LinkKind[] = ["taxonomy", "scheme", "class", "individual", "proposal"];

/**
 * Turn stored messages into display messages: each user question, then one
 * assistant message per turn that merges the turn's model replies and tool
 * results (results attach to their tool call by id).
 */
export function displayMessagesFromStored(stored: StoredChatMessage[]): DisplayMessage[] {
  const display: DisplayMessage[] = [];
  let turn: DisplayMessage | null = null;
  for (const message of stored) {
    const text = message.blocks.filter((b) => b.type === "text").map((b) => b.text);
    if (message.role === "user" && text.length > 0) {
      turn = null;
      display.push({
        id: message.id,
        role: "user",
        blocks: [{ type: "text", text: text.join("\n\n") }],
        createdAt: message.created_at,
      });
      continue;
    }
    if (!turn) {
      turn = { id: message.id, role: "assistant", blocks: [], createdAt: message.created_at };
      display.push(turn);
    }
    for (const block of message.blocks) {
      if (block.type === "text" && message.role === "assistant") {
        turn.blocks.push({ type: "text", text: block.text });
      } else if (block.type === "tool_use") {
        turn.blocks.push({
          type: "tool",
          toolUseId: block.id,
          name: block.name,
          input: block.input,
          status: "running",
          summary: "",
        });
      } else if (block.type === "tool_result") {
        const tool = findTool(turn, block.tool_use_id);
        if (tool) {
          tool.status = block.is_error ? "error" : "success";
          tool.summary = block.summary;
        }
      }
    }
  }
  return display;
}

function findTool(turn: DisplayMessage, toolUseId: string) {
  for (const block of turn.blocks) {
    if (block.type === "tool" && block.toolUseId === toolUseId) return block;
  }
  return undefined;
}

/** Entities from stored tool results and page contexts, which answers may link to. */
export function knownEntitiesFromStored(stored: StoredChatMessage[]): KnownEntities {
  const known: KnownEntities = new Map();
  for (const message of stored) {
    for (const block of message.blocks) {
      if (block.type === "tool_result") addEntities(known, block.entities);
    }
    if (message.page_context) addPageContext(known, message.page_context);
  }
  return known;
}

export function addEntities(known: KnownEntities, entities: EntityRef[]): void {
  for (const entity of entities) known.set(entity.id, entity.kind);
}

export function addPageContext(known: KnownEntities, page: PageContext): void {
  if (page.entity_id && page.entity_kind) known.set(page.entity_id, page.entity_kind);
}

/**
 * Apply one stream event to the assistant message being streamed. Events that
 * don't change the message (message_start, message_end) return it unchanged.
 */
export function applyStreamEvent(message: DisplayMessage, event: ChatStreamEvent): DisplayMessage {
  switch (event.type) {
    case "text_delta": {
      const blocks = [...message.blocks];
      const last = blocks[blocks.length - 1];
      if (last?.type === "text") {
        blocks[blocks.length - 1] = { type: "text", text: last.text + event.text };
      } else {
        blocks.push({ type: "text", text: event.text });
      }
      return { ...message, blocks };
    }
    case "tool_start":
      return {
        ...message,
        blocks: [
          ...message.blocks,
          {
            type: "tool",
            toolUseId: event.tool_use_id,
            name: event.name,
            input: event.input,
            status: "running",
            summary: "",
          },
        ],
      };
    case "tool_end":
      return {
        ...message,
        blocks: message.blocks.map((block) =>
          block.type === "tool" && block.toolUseId === event.tool_use_id
            ? { ...block, status: event.is_error ? "error" : "success", summary: event.summary }
            : block,
        ),
      };
    case "error":
      return { ...message, error: event.message };
    default:
      return message;
  }
}

/**
 * Resolve an answer link `entity:<kind>/<id>` to an entity page or a proposal's
 * review page. Returns null —
 * render plain text — when the id didn't come from this conversation's tool
 * results or page context (so a made-up id never becomes a link), when the kind
 * doesn't match, or when the kind has no page (property).
 */
export function resolveEntityLink(
  href: string | undefined,
  known: KnownEntities,
): { kind: LinkKind; id: string } | null {
  const match = /^entity:([a-z]+)\/(.+)$/.exec(href ?? "");
  if (!match) return null;
  const [, kind, rawId] = match;
  let id: string;
  try {
    id = decodeURIComponent(rawId);
  } catch {
    return null;
  }
  if (!PAGE_KINDS.includes(kind as LinkKind)) return null;
  if (known.get(id) !== kind) return null;
  return { kind: kind as LinkKind, id };
}
