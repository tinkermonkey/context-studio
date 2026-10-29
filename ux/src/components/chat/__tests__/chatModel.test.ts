import { describe, it, expect } from "vitest";
import type { StoredChatMessage } from "@/api/services/chat";
import { linkPath } from "@/lib/entityPaths";
import {
  addEntities,
  applyStreamEvent,
  displayMessagesFromStored,
  knownEntitiesFromStored,
  resolveEntityLink,
  type DisplayMessage,
} from "../chatModel";

const T = "2026-10-25T10:00:00Z";

const STORED: StoredChatMessage[] = [
  {
    id: "m0",
    seq: 0,
    role: "user",
    blocks: [{ type: "text", text: "Which operations are there?" }],
    page_context: { route: "/app/schema/classes/cls-1", entity_kind: "class", entity_id: "cls-1" },
    created_at: T,
  },
  {
    id: "m1",
    seq: 1,
    role: "assistant",
    blocks: [
      { type: "text", text: "Let me look." },
      { type: "tool_use", id: "tu-1", name: "search_entities", input: { query: "Operation" } },
    ],
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
        summary: "Found 1",
        is_error: false,
        entities: [{ id: "ind-1", kind: "individual", title: "Admin Health" }],
      },
    ],
    created_at: T,
  },
  {
    id: "m3",
    seq: 3,
    role: "assistant",
    blocks: [{ type: "text", text: "[Admin Health](entity:individual/ind-1)." }],
    created_at: T,
  },
];

describe("displayMessagesFromStored", () => {
  it("merges a turn's replies and tool results into one assistant message", () => {
    expect(displayMessagesFromStored(STORED)).toEqual([
      {
        id: "m0",
        role: "user",
        blocks: [{ type: "text", text: "Which operations are there?" }],
        createdAt: T,
      },
      {
        id: "m1",
        role: "assistant",
        createdAt: T,
        blocks: [
          { type: "text", text: "Let me look." },
          {
            type: "tool",
            toolUseId: "tu-1",
            name: "search_entities",
            input: { query: "Operation" },
            status: "success",
            summary: "Found 1",
          },
          { type: "text", text: "[Admin Health](entity:individual/ind-1)." },
        ],
      },
    ]);
  });
});

describe("knownEntitiesFromStored / resolveEntityLink", () => {
  const known = knownEntitiesFromStored(STORED);

  it("knows tool-result entities and the page-context entity", () => {
    expect(Object.fromEntries(known)).toEqual({ "ind-1": "individual", "cls-1": "class" });
  });

  it("resolves a link whose id and kind came from the conversation", () => {
    expect(resolveEntityLink("entity:individual/ind-1", known)).toEqual({
      kind: "individual",
      id: "ind-1",
    });
    expect(resolveEntityLink("entity:class/cls-1", known)).toEqual({ kind: "class", id: "cls-1" });
  });

  it("resolves a proposal returned by a tool to its review page", () => {
    const withProposal = new Map(known);
    addEntities(withProposal, [{ id: "prop-1", kind: "proposal", title: "Define Operation" }]);
    const target = resolveEntityLink("entity:proposal/prop-1", withProposal);
    expect(target).toEqual({ kind: "proposal", id: "prop-1" });
    expect(target && linkPath(target.kind, target.id)).toBe("/app/proposals/prop-1");
    expect(resolveEntityLink("entity:proposal/invented", withProposal)).toBeNull();
  });

  it.each([
    ["an unknown (possibly made-up) id", "entity:class/invented-id"],
    ["a kind that doesn't match", "entity:class/ind-1"],
    ["a property, which has no page", "entity:property/ind-1"],
    ["a malformed link", "entity:individual"],
    ["a non-entity link", "https://example.com"],
  ])("rejects %s", (_label, href) => {
    expect(resolveEntityLink(href, known)).toBeNull();
  });
});

describe("applyStreamEvent", () => {
  const empty: DisplayMessage = { id: "a", role: "assistant", blocks: [], createdAt: T };

  it("appends text, tracks tool status, and records errors", () => {
    let message = applyStreamEvent(empty, { type: "text_delta", text: "Look" });
    message = applyStreamEvent(message, { type: "text_delta", text: "ing." });
    message = applyStreamEvent(message, {
      type: "tool_start",
      tool_use_id: "tu-1",
      name: "get_entity",
      input: { id: "x" },
    });
    expect(message.blocks[1]).toMatchObject({ type: "tool", status: "running" });

    message = applyStreamEvent(message, {
      type: "tool_end",
      tool_use_id: "tu-1",
      name: "get_entity",
      summary: "Operation (class)",
      is_error: false,
      entities: [],
    });
    message = applyStreamEvent(message, { type: "text_delta", text: "Done" });
    message = applyStreamEvent(message, { type: "error", message: "Rate limited" });

    expect(message.blocks).toEqual([
      { type: "text", text: "Looking." },
      {
        type: "tool",
        toolUseId: "tu-1",
        name: "get_entity",
        input: { id: "x" },
        status: "success",
        summary: "Operation (class)",
      },
      { type: "text", text: "Done" },
    ]);
    expect(message.error).toBe("Rate limited");
  });
});
