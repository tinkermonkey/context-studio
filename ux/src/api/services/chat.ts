import { BaseService } from "./base";
import axiosInstance from "@/api/client/axios";
import type { components } from "@/api/types";

export type ChatStatus = components["schemas"]["ChatStatusResponse"];
export type Conversation = components["schemas"]["ConversationResponse"];
export type ConversationDetail = components["schemas"]["ConversationDetailResponse"];
export type StoredChatMessage = components["schemas"]["ChatMessageResponse"];
export type SendMessageRequest = components["schemas"]["SendMessageRequest"];
export type PageContext = components["schemas"]["PageContextSchema"];
export type EntityRef = components["schemas"]["EntityRefSchema"];
export type ChatStreamEvent =
  | components["schemas"]["MessageStartEvent"]
  | components["schemas"]["TextDeltaEvent"]
  | components["schemas"]["ToolStartEvent"]
  | components["schemas"]["ToolEndEvent"]
  | components["schemas"]["MessageEndEvent"]
  | components["schemas"]["ErrorEvent"];

/**
 * Parse Server-Sent Events from a stream of text chunks: yields the JSON `data`
 * of each event. Frames are separated by a blank line; `:` lines are keepalive
 * comments.
 */
export async function* parseSseStream(
  chunks: AsyncIterable<string>,
): AsyncGenerator<ChatStreamEvent> {
  let buffer = "";
  for await (const chunk of chunks) {
    buffer += chunk.replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).replace(/^ /, ""))
        .join("\n");
      if (data) yield JSON.parse(data) as ChatStreamEvent;
      boundary = buffer.indexOf("\n\n");
    }
  }
}

async function* decodeBody(body: ReadableStream<Uint8Array>): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
  } finally {
    reader.releaseLock();
  }
}

class ChatApiService extends BaseService {
  async getStatus(): Promise<ChatStatus> {
    return this.get<ChatStatus>("/api/chat/status");
  }

  async listConversations(limit = 20): Promise<Conversation[]> {
    return this.get<Conversation[]>("/api/chat/conversations", { limit });
  }

  async getConversation(id: string): Promise<ConversationDetail> {
    return this.get<ConversationDetail>(`/api/chat/conversations/${encodeURIComponent(id)}`);
  }

  async createConversation(): Promise<Conversation> {
    return this.post<Conversation>("/api/chat/conversations");
  }

  async deleteConversation(id: string): Promise<void> {
    await this.delete<void>(`/api/chat/conversations/${encodeURIComponent(id)}`);
  }

  /**
   * Send a message and stream the assistant's turn. Uses fetch + ReadableStream
   * (EventSource can't POST). Yields each event until the stream ends.
   */
  async *streamMessage(
    conversationId: string,
    request: SendMessageRequest,
    signal?: AbortSignal,
  ): AsyncGenerator<ChatStreamEvent> {
    const baseUrl = axiosInstance.defaults.baseURL ?? "";
    const response = await fetch(
      `${baseUrl}/api/chat/conversations/${encodeURIComponent(conversationId)}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(request),
        signal,
      },
    );
    if (!response.ok || !response.body) {
      let detail = `Chat request failed (HTTP ${response.status})`;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        // keep the status message
      }
      throw new Error(detail);
    }
    yield* parseSseStream(decodeBody(response.body));
  }
}

export const chatService = new ChatApiService();
