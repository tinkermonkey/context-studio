import { describe, it, expect, beforeAll, afterEach, afterAll } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { chatService, parseSseStream, type ChatStreamEvent } from "../chat";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function* chunks(...parts: string[]) {
  for (const part of parts) yield part;
}

async function collect(stream: AsyncIterable<ChatStreamEvent>) {
  const events: ChatStreamEvent[] = [];
  for await (const event of stream) events.push(event);
  return events;
}

function sse(events: object[]): string {
  return events
    .map((e) => `event: ${(e as { type: string }).type}\ndata: ${JSON.stringify(e)}\n\n`)
    .join("");
}

describe("parseSseStream", () => {
  it("yields each event's JSON data, across chunk boundaries", async () => {
    const wire = sse([
      { type: "message_start", conversation_id: "c1" },
      { type: "text_delta", text: "Hel" },
      { type: "text_delta", text: "lo" },
    ]);
    const parts = [wire.slice(0, 7), wire.slice(7, 61), wire.slice(61)];

    expect(await collect(parseSseStream(chunks(...parts)))).toEqual([
      { type: "message_start", conversation_id: "c1" },
      { type: "text_delta", text: "Hel" },
      { type: "text_delta", text: "lo" },
    ]);
  });

  it("skips keepalive comments and handles CRLF line endings", async () => {
    const wire = `: ping\r\n\r\nevent: error\r\ndata: {"type":"error","message":"x"}\r\n\r\n`;

    expect(await collect(parseSseStream(chunks(wire)))).toEqual([{ type: "error", message: "x" }]);
  });
});

describe("chatService.streamMessage", () => {
  it("POSTs the message and streams the turn's events", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/chat/conversations/c1/messages", async ({ request }) => {
        body = await request.json();
        return new HttpResponse(
          sse([
            { type: "message_start", conversation_id: "c1" },
            { type: "message_end", stop_reason: "end_turn", tokens_in: 1, tokens_out: 1 },
          ]),
          { headers: { "Content-Type": "text/event-stream" } },
        );
      }),
    );

    const events = await collect(
      chatService.streamMessage("c1", { text: "hi", page_context: { route: "/app" } }),
    );

    expect(body).toEqual({ text: "hi", page_context: { route: "/app" } });
    expect(events.map((e) => e.type)).toEqual(["message_start", "message_end"]);
  });

  it("throws the server's detail when the request fails", async () => {
    server.use(
      http.post("*/api/chat/conversations/gone/messages", () =>
        HttpResponse.json({ detail: "Conversation not found: gone" }, { status: 404 }),
      ),
    );

    await expect(collect(chatService.streamMessage("gone", { text: "hi" }))).rejects.toThrow(
      "Conversation not found: gone",
    );
  });
});
