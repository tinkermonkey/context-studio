import { describe, it, expect, beforeAll, beforeEach, afterEach, afterAll, vi } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { useChatPanelStore } from "@/stores/chatPanel";
import { useBreadcrumbStore } from "@/stores/breadcrumbs";
import { ChatPanel } from "../ChatPanel";

const navigate = vi.fn();
const router = { pathname: "/app/schema/classes/cls-1" };

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => navigate,
    useRouterState: () => ({ location: { pathname: router.pathname }, status: "idle" }),
  };
});

// The panel is built from Heimdall's chat components; render the real ones
// (the global test mock doesn't stub them).
vi.mock("@tinkermonkey/heimdall-ui", async () => vi.importActual("@tinkermonkey/heimdall-ui"));

const T = "2026-10-25T10:00:00Z";
const STATUS = {
  model: "claude-sonnet-5-5",
  available: true,
  max_tool_rounds: 8,
  available_models: ["claude-sonnet-5-5"],
};

function sse(events: object[]) {
  return new HttpResponse(
    events
      .map((e) => `event: ${(e as { type: string }).type}\ndata: ${JSON.stringify(e)}\n\n`)
      .join(""),
    { headers: { "Content-Type": "text/event-stream" } },
  );
}

const STORED_CONVERSATION = {
  id: "conv-1",
  title: "Operations",
  model: "claude-sonnet-5-5",
  created_at: T,
  updated_at: T,
  messages: [
    {
      id: "m0",
      seq: 0,
      role: "user",
      blocks: [{ type: "text", text: "Which operations are there?" }],
      page_context: null,
      created_at: T,
    },
    {
      id: "m1",
      seq: 1,
      role: "assistant",
      blocks: [{ type: "tool_use", id: "tu-1", name: "list_children", input: { id: "cls-1" } }],
      created_at: T,
    },
    {
      id: "m2",
      seq: 2,
      role: "user",
      blocks: [
        {
          type: "tool_result",
          tool_use_id: "tu-1",
          summary: "2 of 2 under Operation",
          is_error: false,
          entities: [
            { id: "cls-1", kind: "class", title: "Operation" },
            { id: "ind-1", kind: "individual", title: "Admin Health" },
          ],
        },
      ],
      created_at: T,
    },
    {
      id: "m3",
      seq: 3,
      role: "assistant",
      blocks: [
        {
          type: "text",
          text:
            "[Operation](entity:class/cls-1) has [Admin Health](entity:individual/ind-1)," +
            " [Ghost](entity:individual/made-up) and [realizes](entity:property/p-1).",
        },
      ],
      created_at: T,
    },
  ],
};

const server = setupServer(
  http.get("*/api/chat/status", () => HttpResponse.json(STATUS)),
  http.get("*/api/chat/conversations", () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
beforeEach(() => {
  router.pathname = "/app/schema/classes/cls-1";
  navigate.mockReset();
  useChatPanelStore.setState({
    open: true,
    askAbout: null,
    dismissedContextKey: null,
    newChatRequest: 0,
    focusRequest: 0,
  });
  useBreadcrumbStore.setState({
    pathname: "/app/schema/classes/cls-1",
    crumbs: [{ label: "Schema", to: "/app/schema/classes" }, { label: "Operation" }],
  });
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("ChatPanel", () => {
  it("is a labelled complementary region with the model chip", async () => {
    render(<ChatPanel />);

    const panel = screen.getByRole("complementary", { name: "Chat assistant" });
    expect(panel).toHaveAttribute("data-testid", "chat-panel");
    expect(panel).toHaveClass("chat-panel");
    expect(await screen.findByTestId("chat-model-chip")).toHaveTextContent("claude-sonnet-5-5");
    expect(screen.getByRole("button", { name: "Close chat" })).toHaveAttribute(
      "data-testid",
      "chat-close-button",
    );
  });

  it("shows suggestions on an empty thread and the Viewing chip for the page entity", async () => {
    render(<ChatPanel />);

    expect(await screen.findByTestId("chat-empty-thread")).toBeInTheDocument();
    const suggestions = screen.getByTestId("chat-suggestions");
    expect(within(suggestions).getByText("Tell me about Operation")).toBeInTheDocument();
    expect(screen.getByText("Viewing: Operation")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Message the assistant" })).toBeInTheDocument();
  });

  it("asks the user to set up a model when no provider serves it", async () => {
    server.use(
      http.get("*/api/chat/status", () => HttpResponse.json({ ...STATUS, available: false })),
    );
    const user = userEvent.setup();

    render(<ChatPanel />);

    const setup = await screen.findByTestId("chat-setup-required");
    expect(within(setup).getByText("Set up a chat model")).toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "Message the assistant" }),
    ).not.toBeInTheDocument();
    await user.click(within(setup).getByRole("button", { name: "Open Settings" }));
    expect(navigate).toHaveBeenCalledWith({ to: "/app/settings" });
  });

  it("resumes the latest conversation and links only entities the tools returned", async () => {
    server.use(
      http.get("*/api/chat/conversations", () => HttpResponse.json([STORED_CONVERSATION])),
      http.get("*/api/chat/conversations/conv-1", () => HttpResponse.json(STORED_CONVERSATION)),
    );
    const user = userEvent.setup();

    render(<ChatPanel />);

    expect(await screen.findByText("Which operations are there?")).toBeInTheDocument();
    const tool = screen.getByTestId("chat-tool-block");
    expect(tool).toHaveAttribute("data-status", "success");
    expect(tool).toHaveTextContent("list_children");

    const links = screen.getAllByTestId("chat-entity-link");
    expect(links.map((a) => [a.textContent, a.getAttribute("href")])).toEqual([
      ["Operation", "/app/schema/classes/cls-1"],
      ["Admin Health", "/app/data/individuals/ind-1"],
    ]);
    // A made-up id and a property (no page) render as plain text
    const plain = screen.getAllByTestId("chat-entity-text").map((s) => s.textContent);
    expect(plain).toEqual(["Ghost", "realizes"]);

    await user.click(links[1]);
    expect(navigate).toHaveBeenCalledWith({ to: "/app/data/individuals/ind-1" });
    expect(useChatPanelStore.getState().open).toBe(true);
  });

  it("streams a turn with tool activity, sending the page context", async () => {
    let sent: unknown;
    server.use(
      http.post("*/api/chat/conversations", () =>
        HttpResponse.json(
          { id: "conv-new", title: "New chat", model: "m", created_at: T, updated_at: T },
          { status: 201 },
        ),
      ),
      http.post("*/api/chat/conversations/conv-new/messages", async ({ request }) => {
        sent = await request.json();
        return sse([
          { type: "message_start", conversation_id: "conv-new" },
          { type: "tool_start", tool_use_id: "tu-1", name: "get_entity", input: { id: "cls-1" } },
          {
            type: "tool_end",
            tool_use_id: "tu-1",
            name: "get_entity",
            summary: "Operation (class)",
            is_error: false,
            entities: [{ id: "cls-1", kind: "class", title: "Operation" }],
          },
          { type: "text_delta", text: "[Operation](entity:class/cls-1) is an " },
          { type: "text_delta", text: "API class." },
          { type: "message_end", stop_reason: "end_turn", tokens_in: 1, tokens_out: 1 },
        ]);
      }),
    );
    const user = userEvent.setup();

    render(<ChatPanel />);

    const box = await screen.findByRole("textbox", { name: "Message the assistant" });
    await user.type(box, "What is this?{Enter}");

    expect(await screen.findByText("is an API class.", { exact: false })).toBeInTheDocument();
    expect(sent).toEqual({
      text: "What is this?",
      page_context: {
        route: "/app/schema/classes/cls-1",
        entity_kind: "class",
        entity_id: "cls-1",
      },
    });
    expect(screen.getByTestId("chat-tool-block")).toHaveAttribute("data-status", "success");
    expect(screen.getByTestId("chat-entity-link")).toHaveAttribute(
      "href",
      "/app/schema/classes/cls-1",
    );
    expect(box).toHaveValue("");
  });

  it("removing the Viewing chip stops sending the page context", async () => {
    let sent: { page_context?: unknown } = {};
    server.use(
      http.post("*/api/chat/conversations", () =>
        HttpResponse.json(
          { id: "c2", title: "t", model: "m", created_at: T, updated_at: T },
          { status: 201 },
        ),
      ),
      http.post("*/api/chat/conversations/c2/messages", async ({ request }) => {
        sent = (await request.json()) as typeof sent;
        return sse([{ type: "message_end", stop_reason: "end_turn", tokens_in: 0, tokens_out: 0 }]);
      }),
    );
    const user = userEvent.setup();

    render(<ChatPanel />);

    await user.click(await screen.findByRole("button", { name: "Remove Viewing: Operation" }));
    expect(screen.queryByText("Viewing: Operation")).not.toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Message the assistant" }), "hi{Enter}");

    await waitFor(() => expect(sent.page_context).toBeNull());
  });

  it("shows a turn error inline", async () => {
    server.use(
      http.post("*/api/chat/conversations", () =>
        HttpResponse.json(
          { id: "c3", title: "t", model: "m", created_at: T, updated_at: T },
          { status: 201 },
        ),
      ),
      http.post("*/api/chat/conversations/c3/messages", () =>
        sse([
          { type: "message_start", conversation_id: "c3" },
          { type: "error", message: "The chat model provider is rate limiting requests." },
        ]),
      ),
    );
    const user = userEvent.setup();

    render(<ChatPanel />);
    await user.type(
      await screen.findByRole("textbox", { name: "Message the assistant" }),
      "hi{Enter}",
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("rate limiting");
  });

  it("New chat clears the thread", async () => {
    server.use(
      http.get("*/api/chat/conversations", () => HttpResponse.json([STORED_CONVERSATION])),
      http.get("*/api/chat/conversations/conv-1", () => HttpResponse.json(STORED_CONVERSATION)),
    );

    render(<ChatPanel />);
    await screen.findByText("Which operations are there?");

    act(() => useChatPanelStore.getState().requestNewChat());

    expect(await screen.findByTestId("chat-empty-thread")).toBeInTheDocument();
    expect(screen.queryByText("Which operations are there?")).not.toBeInTheDocument();
  });

  it("is hidden while closed", async () => {
    useChatPanelStore.setState({ open: false });

    render(<ChatPanel />);

    expect(screen.getByTestId("chat-panel")).not.toBeVisible();
  });
});
