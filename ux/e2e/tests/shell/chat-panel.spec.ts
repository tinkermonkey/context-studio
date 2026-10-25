import type { Page, Route } from "@playwright/test";
import { test, expect } from "../../fixtures/app-test";
import {
  createClass,
  createConceptScheme,
  createIndividual,
  createTaxonomy,
} from "../../fixtures/factories";

// The chat panel is a docked right column (complementary region "Chat
// assistant"). The test stack has no live model, so the chat API is mocked at
// the network layer: /status, the conversation list, conversation creation and
// the SSE message stream. Everything else (entity pages, navigation, the
// shell) is the real app against the isolated test backend.

const PANEL = '[data-testid="chat-panel"]';

interface ChatMockOptions {
  available?: boolean;
  /** Stream events for each sent message; receives the request body. */
  onMessage?: (body: { text: string; page_context?: unknown }) => object[];
}

async function mockChatApi(page: Page, options: ChatMockOptions = {}) {
  const sent: Array<{ text: string; page_context?: unknown }> = [];
  const now = new Date().toISOString();
  await page.route("**/api/chat/status", (route) =>
    route.fulfill({
      json: {
        model: "claude-sonnet-5-5",
        available: options.available ?? true,
        max_tool_rounds: 8,
        available_models: ["claude-sonnet-5-5"],
      },
    }),
  );
  await page.route("**/api/chat/conversations?*", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/chat/conversations", (route) =>
    route.fulfill({
      status: 201,
      json: {
        id: "e2e-conv",
        title: "New chat",
        model: "claude-sonnet-5-5",
        created_at: now,
        updated_at: now,
      },
    }),
  );
  await page.route("**/api/chat/conversations/e2e-conv/messages", async (route: Route) => {
    const body = route.request().postDataJSON();
    sent.push(body);
    const events = options.onMessage?.(body) ?? [];
    await route.fulfill({
      headers: { "Content-Type": "text/event-stream" },
      body: events
        .map((e) => `event: ${(e as { type: string }).type}\ndata: ${JSON.stringify(e)}\n\n`)
        .join(""),
    });
  });
  return sent;
}

async function seedClassWithIndividual(page: Page) {
  const taxonomy = await createTaxonomy(page, { title: "Chat E2E Taxonomy" });
  const scheme = await createConceptScheme(page, taxonomy.id, { title: "API Layer" });
  const cls = await createClass(page, scheme.id, { title: "Operation" });
  const individual = await createIndividual(page, {
    title: "Admin Health",
    class_ids: [cls.id],
  });
  return { cls, individual };
}

test.describe("Chat panel", () => {
  test("opens with ⌘J, sends the page context, and follows entity links with the panel open", async ({
    page,
  }) => {
    const { cls, individual } = await seedClassWithIndividual(page);
    const sent = await mockChatApi(page, {
      onMessage: () => [
        { type: "message_start", conversation_id: "e2e-conv" },
        { type: "tool_start", tool_use_id: "tu-1", name: "list_children", input: { id: cls.id } },
        {
          type: "tool_end",
          tool_use_id: "tu-1",
          name: "list_children",
          summary: "1 of 1 under Operation",
          is_error: false,
          entities: [
            { id: cls.id, kind: "class", title: "Operation" },
            { id: individual.id, kind: "individual", title: "Admin Health" },
          ],
        },
        {
          type: "text_delta",
          text: `[Operation](entity:class/${cls.id}) has one individual: `,
        },
        {
          type: "text_delta",
          text: `[Admin Health](entity:individual/${individual.id}). [Ghost](entity:individual/not-a-real-id) is not linked.`,
        },
        { type: "message_end", stop_reason: "end_turn", tokens_in: 10, tokens_out: 5 },
      ],
    });

    await page.goto(`/app/schema/classes/${cls.id}`);
    await expect(page.getByRole("heading", { name: "Operation", level: 1 })).toBeVisible();

    await page.keyboard.press("Meta+j");
    const panel = page.getByRole("complementary", { name: "Chat assistant" });
    await expect(panel).toBeVisible();
    await expect(page.getByTestId("app-chat-layout")).toHaveClass(/app-chat-layout--open/);
    await expect(page.getByTestId("topbar-chat-button")).toHaveAttribute("aria-pressed", "true");
    await expect(panel.getByText("Viewing: Operation")).toBeVisible();

    const composer = panel.getByRole("textbox", { name: "Message the assistant" });
    await composer.fill("Which individuals does this class have?");
    await composer.press("Enter");

    await expect(panel.getByTestId("chat-message-user")).toContainText(
      "Which individuals does this class have?",
    );
    await expect(panel.getByTestId("chat-tool-block")).toHaveAttribute("data-status", "success");
    const link = panel.getByRole("link", { name: "Admin Health" });
    await expect(link).toHaveAttribute("href", `/app/data/individuals/${individual.id}`);
    await expect(panel.getByTestId("chat-entity-text")).toHaveText("Ghost");
    expect(sent[0]).toEqual({
      text: "Which individuals does this class have?",
      page_context: {
        route: `/app/schema/classes/${cls.id}`,
        entity_kind: "class",
        entity_id: cls.id,
      },
    });

    await link.click();
    await expect(page).toHaveURL(new RegExp(`/app/data/individuals/${individual.id}$`));
    await expect(page.getByRole("heading", { name: "Admin Health", level: 1 })).toBeVisible();
    await expect(panel).toBeVisible();
    await expect(panel.getByText("Viewing: Admin Health")).toBeVisible();
    // The conversation is still there after navigating
    await expect(panel.getByTestId("chat-message-user")).toBeVisible();
  });

  test("“Ask about this” on an entity page opens the panel on that entity", async ({ page }) => {
    const { individual } = await seedClassWithIndividual(page);
    await mockChatApi(page);

    await page.goto(`/app/data/individuals/${individual.id}`);
    await expect(page.getByRole("heading", { name: "Admin Health", level: 1 })).toBeVisible();
    await expect(page.locator(PANEL)).toHaveCount(0);

    await page.getByRole("button", { name: "Ask about this" }).click();

    const panel = page.getByRole("complementary", { name: "Chat assistant" });
    await expect(panel).toBeVisible();
    await expect(panel.getByText("Viewing: Admin Health")).toBeVisible();
    await expect(panel.getByRole("textbox", { name: "Message the assistant" })).toBeFocused();
    await expect(panel.getByTestId("chat-suggestions")).toBeVisible();
  });

  test("the topbar button toggles the panel and the open state survives a reload", async ({
    page,
  }) => {
    await mockChatApi(page);
    await page.goto("/app");
    const button = page.getByTestId("topbar-chat-button");
    await expect(button).toHaveAttribute("aria-pressed", "false");

    await button.click();
    await expect(page.locator(PANEL)).toBeVisible();
    await expect(button).toHaveAttribute("aria-pressed", "true");

    await page.reload();
    await expect(page.locator(PANEL)).toBeVisible();

    await page.getByTestId("chat-close-button").click();
    await expect(page.locator(PANEL)).toBeHidden();
    await expect(button).toHaveAttribute("aria-pressed", "false");
  });

  test("the palette's “Ask about this page” action opens the panel", async ({ page }) => {
    await mockChatApi(page);
    await page.goto("/app");
    await page.waitForLoadState("networkidle");

    await page.keyboard.press("Meta+k");
    await page.locator(".command-palette__input").fill("Ask about this page");
    await page.locator(".command-palette__item").first().click();

    await expect(page.locator(PANEL)).toBeVisible();
    await expect(page.locator(PANEL).getByText("Viewing: Dashboard")).toBeVisible();
  });

  test("asks for setup when no provider serves the model, linking to the chat model setting", async ({
    page,
  }) => {
    await mockChatApi(page, { available: false });
    await page.goto("/app");
    await page.getByTestId("topbar-chat-button").click();

    const setup = page.getByTestId("chat-setup-required");
    await expect(setup).toContainText("Set up a chat model");
    await setup.getByRole("button", { name: "Open Settings" }).click();

    await expect(page).toHaveURL(/\/app\/settings$/);
    await expect(page.getByTestId("settings-chat-model-input")).toBeVisible();
  });
});
