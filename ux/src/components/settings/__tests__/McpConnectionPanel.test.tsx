import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { render } from "@/test/test-utils";
import { createMcpConnection } from "@/api/services/__tests__/fixtures/admin.fixtures";
import { ToastViewport, useToasts } from "@/components/ui/Toast";
import { McpConnectionPanel } from "../McpConnectionPanel";

function PanelWithToasts() {
  const { toasts, dismiss } = useToasts();
  return (
    <>
      <McpConnectionPanel />
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </>
  );
}

const CONNECTION = createMcpConnection({
  url: "http://127.0.0.1:8000/mcp",
  auth_token: "tok_secret_123",
});
const FULL_COMMAND =
  'claude mcp add --transport http context-studio http://127.0.0.1:8000/mcp --header "Authorization: Bearer tok_secret_123"';

const server = setupServer(http.get("*/api/v1/admin/mcp", () => HttpResponse.json(CONNECTION)));

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });
});

afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});

afterAll(() => {
  server.close();
});

describe("McpConnectionPanel", () => {
  it("renders the root testid and the endpoint URL", async () => {
    render(<McpConnectionPanel />);

    expect(screen.getByTestId("mcp-connection-panel")).toBeInTheDocument();
    expect(await screen.findByTestId("mcp-connection-url")).toHaveValue(CONNECTION.url);
    expect(screen.getByTestId("mcp-connection-note")).toHaveAttribute("role", "note");
  });

  it("masks the token and the command until the token is revealed", async () => {
    const user = userEvent.setup();
    render(<McpConnectionPanel />);

    const token = await screen.findByTestId("mcp-connection-token");
    const toggle = screen.getByTestId("mcp-connection-token-toggle");
    const command = screen.getByTestId("mcp-connection-command");

    expect(token).toHaveAttribute("type", "password");
    expect(token).toHaveValue("tok_secret_123");
    expect(command).not.toHaveTextContent("tok_secret_123");
    expect(command).toHaveClass("mcp-connection-command");
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(toggle).toHaveAttribute("aria-label", "Show token");

    await user.click(toggle);

    expect(token).toHaveAttribute("type", "text");
    expect(command).toHaveTextContent(FULL_COMMAND);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    expect(toggle).toHaveAttribute("aria-label", "Hide token");
  });

  it("copies the full command with the real token, even while masked", async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    render(<PanelWithToasts />);

    const copy = await screen.findByTestId("mcp-connection-copy-command");
    expect(copy).toHaveAttribute("aria-label", "Copy the claude mcp add command");

    await user.click(copy);

    expect(writeText).toHaveBeenCalledWith(FULL_COMMAND);
    expect(await screen.findByText("Command copied to clipboard")).toBeInTheDocument();
  });

  it("explains when the connection details are refused", async () => {
    server.use(
      http.get("*/api/v1/admin/mcp", () =>
        HttpResponse.json({ detail: "Local clients only" }, { status: 403 }),
      ),
    );

    render(<McpConnectionPanel />);

    expect(
      await screen.findByText(
        "MCP connection details are only available when the app runs locally",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("mcp-connection-token")).not.toBeInTheDocument();
  });
});
